"""
TG Sender — Telethon sending engine with MTProto proxy
Supports: multiple templates, random selection, flood handling, single test send
"""
import asyncio
import os
import sqlite3
import random
import time
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "sender.db"
SESSIONS_DIR = ROOT / "sessions"
PROXY_CONF = ROOT / "proxy.conf"

API_ID = int(os.environ.get("TG_SENDER_API_ID", "2040") or "2040")
API_HASH = os.environ.get("TG_SENDER_API_HASH", "b18441a1ff607e10a989891a5462e627") or "b18441a1ff607e10a989891a5462e627"


def get_proxy():
    if not PROXY_CONF.exists():
        return None, None, None
    line = PROXY_CONF.read_text().strip()
    parts = line.split(":")
    if len(parts) >= 3:
        return parts[0], int(parts[1]), parts[2]
    return None, None, None


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_active_accounts():
    conn = get_db()
    accounts = conn.execute(
        "SELECT * FROM tg_accounts WHERE status = 'active'"
    ).fetchall()
    conn.close()
    return [dict(a) for a in accounts]


def get_templates():
    conn = get_db()
    templates = conn.execute("SELECT * FROM message_templates").fetchall()
    conn.close()
    return [dict(t) for t in templates]


def get_contacts_for_campaign(campaign_id):
    conn = get_db()
    campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not campaign:
        conn.close()
        return [], None
    campaign = dict(campaign)

    group = campaign.get("contact_group", "all")
    if group and group != "all":
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE group_name = ? AND status = 'active'", (group,)
        ).fetchall()
    else:
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE status = 'active'"
        ).fetchall()

    contacted = conn.execute(
        "SELECT contact_username FROM message_log WHERE campaign_id = ? AND status = 'sent'", (campaign_id,)
    ).fetchall()
    contacted_set = {c["contact_username"] for c in contacted}

    result = [dict(c) for c in contacts if c["username"] not in contacted_set]
    conn.close()
    return result, campaign


def log_message(campaign_id, account_id, contact_username, status, error=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO message_log (campaign_id, account_id, contact_username, status, error_message) VALUES (?, ?, ?, ?, ?)",
        (campaign_id, account_id, contact_username, status, error)
    )
    conn.commit()
    conn.close()


def update_campaign_progress(campaign_id):
    conn = get_db()
    sent = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE campaign_id = ? AND status = 'sent'", (campaign_id,)
    ).fetchone()[0]
    failed = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE campaign_id = ? AND status = 'failed'", (campaign_id,)
    ).fetchone()[0]
    conn.execute("UPDATE campaigns SET sent_count = ?, failed_count = ? WHERE id = ?", (sent, failed, campaign_id))
    conn.commit()
    conn.close()


async def send_message(account, username, text):
    """Send message via Telethon. Returns (ok, error, flood_seconds)."""
    host, port, secret = get_proxy()
    phone = account["phone"].replace("+", "")
    session_path = str(SESSIONS_DIR / phone)

    client = None
    try:
        proxy = None
        if host:
            proxy = (host, port, secret)

        client = TelegramClient(
            session_path, account["api_id"], account["api_hash"],
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy, connection_retries=1, timeout=15,
        )
        await asyncio.wait_for(client.connect(), timeout=20)

        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Not authorized", 0

        try:
            entity = await client.get_entity(username)
        except Exception as e:
            await client.disconnect()
            return False, "User not found: " + str(e)[:30], 0

        await client.send_message(entity, text)
        await client.disconnect()
        return True, None, 0

    except Exception as e:
        err = str(e)
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass

        if "flood" in err.lower() or "Too many requests" in err or "PeerFlood" in err:
            import re
            match = re.search(r"(\d+)\s*second", err)
            seconds = int(match.group(1)) if match else 300
            if "PeerFlood" in err:
                seconds = 3600
            return False, "FLOOD_WAIT:" + str(seconds), seconds

        return False, err[:100], 0


async def send_single_test(account_phone, target_username, text):
    """Send a single test message."""
    conn = get_db()
    account = conn.execute("SELECT * FROM tg_accounts WHERE phone = ?", (account_phone,)).fetchone()
    conn.close()

    if not account:
        return False, "Account not found", 0

    return await send_message(dict(account), target_username, text)


async def run_campaign(campaign_id):
    """Run a full campaign with multiple templates and flood handling."""
    contacts, campaign = get_contacts_for_campaign(campaign_id)
    if not campaign:
        return {"error": "No campaign found"}

    accounts = get_active_accounts()
    if not accounts:
        return {"error": "No active accounts"}

    all_templates = get_templates()
    if not all_templates:
        return {"error": "No templates"}

    campaign_template_id = campaign.get("template_id")
    templates_to_use = [t for t in all_templates if t["id"] == campaign_template_id] if campaign_template_id else all_templates
    if not templates_to_use:
        templates_to_use = all_templates

    delay_min = campaign.get("delay_min", 30)
    delay_max = campaign.get("delay_max", 60)
    messages_per_account = campaign.get("messages_per_account", 20)

    conn = get_db()
    conn.execute(
        "UPDATE campaigns SET status = 'running', started_at = ?, total_contacts = ? WHERE id = ?",
        (datetime.now().isoformat(), len(contacts), campaign_id)
    )
    conn.commit()
    conn.close()

    results = {"sent": 0, "failed": 0, "errors": []}
    account_index = 0
    messages_on_current = 0
    flood_until = {}  # phone -> timestamp

    for contact in contacts:
        conn = get_db()
        c = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        conn.close()
        if not c or c["status"] != "running":
            break

        username = contact["username"]
        template = random.choice(templates_to_use)
        text = template["text"]
        text = text.replace("{name}", contact.get("name") or username)
        text = text.replace("{username}", username)

        # Try each account until success or all exhausted
        sent_ok = False
        attempts = 0
        max_attempts = len(accounts)

        while not sent_ok and attempts < max_attempts:
            # Find available (non-flooded) accounts
            available = [a for a in accounts if flood_until.get(a["phone"], 0) < time.time()]

            if not available:
                # All flooded - wait for soonest
                if flood_until:
                    min_wait = min(flood_until.values()) - time.time()
                    if min_wait > 0:
                        await asyncio.sleep(min(min_wait + 5, 300))
                    flood_until.clear()
                available = accounts

            # Rotate accounts
            if messages_on_current >= messages_per_account:
                account_index = (account_index + 1) % len(available)
                messages_on_current = 0

            account = available[account_index % len(available)]

            ok, error, flood_seconds = await send_message(account, username, text)

            if ok:
                results["sent"] += 1
                log_message(campaign_id, account["id"], username, "sent")
                conn = get_db()
                conn.execute(
                    "UPDATE contacts SET status = 'contacted', last_contacted = ? WHERE id = ?",
                    (datetime.now().isoformat(), contact["id"])
                )
                conn.commit()
                conn.close()
                sent_ok = True
                messages_on_current += 1
            elif "FLOOD" in str(error):
                # Mark account as flooded and try next
                flood_until[account["phone"]] = time.time() + flood_seconds
                log_message(campaign_id, account["id"], username, "flood_wait", error)
                account_index = (account_index + 1) % len(accounts)
                messages_on_current = 0
                attempts += 1
            else:
                results["failed"] += 1
                results["errors"].append(username + ": " + str(error))
                log_message(campaign_id, account["id"], username, "failed", error)
                attempts += 1

        update_campaign_progress(campaign_id)

        # Delay between successful sends
        if sent_ok:
            delay = random.uniform(delay_min, delay_max)
            await asyncio.sleep(delay)

    conn = get_db()
    conn.execute(
        "UPDATE campaigns SET status = 'completed', completed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), campaign_id)
    )
    conn.commit()
    conn.close()

    return results


def start_campaign_async(campaign_id):
    loop = asyncio.new_event_loop()

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_campaign(campaign_id))
        loop.close()

    import threading
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return True


def send_test_async(account_phone, target_username, text):
    loop = asyncio.new_event_loop()

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_single_test(account_phone, target_username, text))
        loop.close()

    import threading
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return True
