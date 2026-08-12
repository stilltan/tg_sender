"""
TG Sender — Telethon sending engine with MTProto proxy
"""
import asyncio
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

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"


def get_proxy():
    """Read proxy config from file."""
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
    """Get active accounts from DB."""
    conn = get_db()
    accounts = conn.execute(
        "SELECT * FROM tg_accounts WHERE status = 'active'"
    ).fetchall()
    conn.close()
    return [dict(a) for a in accounts]


def get_contacts_for_campaign(campaign_id):
    """Get contacts that haven't been contacted in this campaign."""
    conn = get_db()
    campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not campaign:
        conn.close()
        return [], None

    campaign = dict(campaign)

    # Get template
    template = conn.execute("SELECT * FROM message_templates WHERE id = ?", (campaign["template_id"],)).fetchone()
    template = dict(template) if template else None

    # Get contacts
    group = campaign.get("contact_group", "all")
    if group and group != "all":
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE group_name = ? AND status = 'active'",
            (group,)
        ).fetchall()
    else:
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE status = 'active'"
        ).fetchall()

    # Exclude already contacted in this campaign
    contacted = conn.execute(
        "SELECT contact_username FROM message_log WHERE campaign_id = ? AND status = 'sent'",
        (campaign_id,)
    ).fetchall()
    contacted_set = {c["contact_username"] for c in contacted}

    result = [dict(c) for c in contacts if c["username"] not in contacted_set]
    conn.close()
    return result, template


def log_message(campaign_id, account_phone, contact_username, status, error=None):
    """Log a sent message."""
    conn = get_db()
    conn.execute(
        "INSERT INTO message_log (campaign_id, account_id, contact_username, status, error_message) VALUES (?, ?, ?, ?, ?)",
        (campaign_id, 0, contact_username, status, error)
    )
    conn.commit()
    conn.close()


def update_campaign_progress(campaign_id):
    """Update campaign sent/failed counts."""
    conn = get_db()
    sent = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE campaign_id = ? AND status = 'sent'",
        (campaign_id,)
    ).fetchone()[0]
    failed = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE campaign_id = ? AND status = 'failed'",
        (campaign_id,)
    ).fetchone()[0]
    conn.execute(
        "UPDATE campaigns SET sent_count = ?, failed_count = ? WHERE id = ?",
        (sent, failed, campaign_id)
    )
    conn.commit()
    conn.close()


async def send_message(account, username, text):
    """Send a message via Telethon through MTProto proxy."""
    host, port, secret = get_proxy()
    session_path = str(SESSIONS_DIR / account["phone"].replace("+", ""))

    try:
        proxy = None
        if host:
            proxy = (host, port, secret)

        client = TelegramClient(
            session_path, account["api_id"], account["api_hash"],
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy,
            connection_retries=2,
            timeout=15,
        )
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Account not authorized"

        # Get entity
        try:
            entity = await client.get_entity(username)
        except Exception as e:
            await client.disconnect()
            return False, f"User not found: {str(e)[:30]}"

        # Send message
        await client.send_message(entity, text)
        await client.disconnect()
        return True, None

    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, str(e)[:100]


async def run_campaign(campaign_id):
    """Run a full campaign."""
    contacts, template = get_contacts_for_campaign(campaign_id)
    if not template:
        return {"error": "No template found"}

    accounts = get_active_accounts()
    if not accounts:
        return {"error": "No active accounts"}

    conn = get_db()
    campaign = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    campaign = dict(campaign)
    conn.close()

    delay_min = campaign.get("delay_min", 30)
    delay_max = campaign.get("delay_max", 60)
    messages_per_account = campaign.get("messages_per_account", 20)

    # Update campaign status
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

    for contact in contacts:
        # Check if campaign still running
        conn = get_db()
        c = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        conn.close()
        if not c or c["status"] != "running":
            break

        # Account rotation
        if messages_on_current >= messages_per_account:
            account_index = (account_index + 1) % len(accounts)
            messages_on_current = 0

        account = accounts[account_index]
        username = contact["username"]
        text = template["text"]

        # Replace placeholders
        text = text.replace("{name}", contact.get("name") or username)
        text = text.replace("{username}", username)

        # Send
        ok, error = await send_message(account, username, text)

        if ok:
            results["sent"] += 1
            log_message(campaign_id, account["phone"], username, "sent")

            # Update contact status
            conn = get_db()
            conn.execute(
                "UPDATE contacts SET status = 'contacted', last_contacted = ? WHERE id = ?",
                (datetime.now().isoformat(), contact["id"])
            )
            conn.commit()
            conn.close()
        else:
            results["failed"] += 1
            results["errors"].append(f"{username}: {error}")
            log_message(campaign_id, account["phone"], username, "failed", error)

        messages_on_current += 1
        update_campaign_progress(campaign_id)

        # Delay
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
    """Start campaign in background."""
    loop = asyncio.new_event_loop()

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_campaign(campaign_id))
        loop.close()

    import threading
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return True
