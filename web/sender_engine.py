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
    session_path = str(SESSIONS_DIR / account["phone"].replace("+", ""))

    try:
        proxy = None
        if host:
            proxy = (host, port, secret)

        client = TelegramClient(
            session_path, account["api_id"], account["api_hash"],
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy, connection_retries=2, timeout=15,
        )
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Account not authorized", 0

        try:
            entity = await client.get_entity(username)
        except Exception as e:
            await client.disconnect()
            return False, f"User not found: {str(e)[:30]}", 0

        await client.send_message(entity, text)
        await client.disconnect()
        return True, None, 0

    except Exception as e:
        err = str(e)
        try:
            await client.disconnect()
        except:
            pass

        # Detect flood wait
        if "flood" in err.lower() or "Too many requests" in err:
            # Extract seconds
            import re
            match = re.search(r'(\d+)\s*second', err)
            seconds = int(match.group(1)) if match else 300
            return False, f"FLOOD_WAIT:{seconds}", seconds

        if "PeerFlood" in err:
            return False, "PEER_FLOOD:account restricted", 3600

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

    # Get all templates for random selection
    all_templates = get_templates()
    if not all_templates:
        return {"error": "No templates"}

    # Filter templates if campaign has specific ones
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
    flood_until = {}  # account_phone -> timestamp when flood ends

    for contact in contacts:
        # Check campaign status
        conn = get_db()
        c = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        conn.close()
        if not c or c["status"] != "running":
            break

        # Find available account (skip flooded ones)
        available_accounts = [a for a in accounts if flood_until.get(a["phone"], 0) < time.time()]
        if not available_accounts:
            # All accounts flooded, wait
            min_wait = min(flood_until.values()) - time.time()
            if min_wait > 0:
                await asyncio.sleep(min(min_wait + 5, 300))
            available_accounts = accounts

        if messages_on_current >= messages_per_account:
            account_index = (account_index + 1) % len(available_accounts)
            messages_on_current = 0

        account = available_accounts[account_index % len(available_accounts)]
        username = contact["username"]

        # Pick random template
        template = random.choice(templates_to_use)
        text = template["text"]
        text = text.replace("{name}", contact.get("name") or username)
        text = text.replace("{username}", username)

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
        elif "FLOOD" in str(error) or "PEER_FLOOD" in str(error):
            results["failed"] += 1
            results["errors"].append(f"{username}: {error}")
            log_message(campaign_id, account["id"], username, "flood_wait", error)
            # Mark account as flooded
            flood_until[account["phone"]] = time.time() + flood_seconds
            # Try next account
            account_index = (account_index + 1) % len(accounts)
            messages_on_current = 0
        else:
            results["failed"] += 1
            results["errors"].append(f"{username}: {error}")
            log_message(campaign_id, account["id"], username, "failed", error)

        messages_on_current += 1
        update_campaign_progress(campaign_id)

        # Random delay
        delay = random.uniform(delay_min, delay_max)
        await asyncio.sleep(delay)

    # Mark completed
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
        result = loop.run_until_complete(send_single_test(account_phone, target_username, text))
        loop.close()
        return result

    import threading
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return True
