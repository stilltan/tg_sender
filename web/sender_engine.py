"""
TG Sender — Telethon sending engine with MTProto proxy
Full anti-spam protection: spintax, smart delays, daily limits, flood handling
"""
import asyncio
import os
import sqlite3
import random
import time
import re
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


# ============================================================
# SPINTAX ENGINE
# ============================================================

def spintax(text: str) -> str:
    """Process spintax: {option1|option2|option3} -> random choice."""
    def replace(match):
        options = match.group(1).split('|')
        return random.choice(options)
    
    for _ in range(5):
        new_text = re.sub(r'\{([^{}]+)\}', replace, text)
        if new_text == text:
            break
        text = new_text
    
    return text


def generate_unique_text(template: str, name: str = "", username: str = "") -> str:
    """Generate unique text from spintax template."""
    text = spintax(template)
    text = text.replace("{name}", name or username)
    text = text.replace("{username}", username)
    return text.strip()


# ============================================================
# SMART DELAYS
# ============================================================

def get_smart_delay(account_age_days: int, messages_today: int, is_first: bool = False) -> float:
    """Smart random delay based on account age and activity."""
    if account_age_days < 7:
        base_min, base_max = 180, 600
    elif account_age_days < 14:
        base_min, base_max = 120, 420
    elif account_age_days < 30:
        base_min, base_max = 90, 300
    elif account_age_days < 90:
        base_min, base_max = 60, 180
    else:
        base_min, base_max = 45, 150
    
    if is_first:
        base_min *= 1.5
        base_max *= 2.0
    
    if messages_today > 20:
        base_min *= 1.3
        base_max *= 1.5
    elif messages_today > 10:
        base_min *= 1.1
        base_max *= 1.2
    
    delay = random.uniform(base_min, base_max)
    
    # 5% chance of long pause
    if random.random() < 0.05:
        delay += random.uniform(600, 1800)
    
    # 2% chance of very long pause
    if random.random() < 0.02:
        delay += random.uniform(1800, 3600)
    
    return delay


def get_typing_delay(text_length: int) -> float:
    """Simulate typing time."""
    base = text_length / 3.3
    return min(base * random.uniform(0.7, 1.3), 30)


# ============================================================
# DAILY LIMITS
# ============================================================

LIMITS_BY_AGE = {
    0: 3, 3: 5, 7: 8, 14: 12, 30: 20, 60: 30, 90: 40, 180: 60, 365: 80,
}


def get_daily_limit(age_days: int) -> int:
    limit = 3
    for threshold, val in sorted(LIMITS_BY_AGE.items()):
        if age_days >= threshold:
            limit = val
    return limit


def get_account_age_days(created_at: str) -> int:
    if not created_at:
        return 0
    try:
        created = datetime.fromisoformat(created_at.split('+')[0])
        return (datetime.now() - created).days
    except Exception:
        return 0


def get_messages_today(account_id: int) -> int:
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    count = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE account_id = ? AND status = 'sent' AND date(sent_at) = ?",
        (account_id, today)
    ).fetchone()[0]
    conn.close()
    return count


def is_account_available(account_id: int, created_at: str) -> tuple:
    age = get_account_age_days(created_at)
    limit = get_daily_limit(age)
    sent = get_messages_today(account_id)
    return sent < limit, f"{sent}/{limit}"


# ============================================================
# FIRST MESSAGE CHECK
# ============================================================

def check_first_message(text: str) -> tuple:
    """Check if first message is safe. Returns (safe, reason)."""
    text_lower = text.lower()
    
    # No links in first message
    for pattern in ['http://', 'https://', 't.me/', 'telegram.me/', 'www.']:
        if pattern in text_lower:
            return False, "Ссылки в первом сообщении запрещены"
    
    # Not too long
    if len(text) > 500:
        return False, "Первое сообщение слишком длинное (макс 500)"
    
    # No spam words
    spam_words = ['заработок', 'доход', 'миллион', 'бесплатно', 'акция',
                  'скидка', 'промокод', 'крипто', 'bitcoin', 'инвестиции']
    for word in spam_words:
        if word in text_lower:
            return False, f"Спам-слово: {word}"
    
    # No CAPS spam
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.5 and len(text) > 20:
        return False, "Слишком много заглавных букв"
    
    return True, "OK"


def is_first_contact(username: str) -> bool:
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM message_log WHERE contact_username = ? AND status = 'sent'",
        (username,)
    ).fetchone()[0]
    conn.close()
    return count == 0


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_proxy():
    if not PROXY_CONF.exists():
        return None, None, None
    line = PROXY_CONF.read_text().strip()
    parts = line.split(":")
    if len(parts) >= 3:
        return parts[0], int(parts[1]), parts[2]
    return None, None, None


def get_active_accounts():
    conn = get_db()
    accounts = conn.execute("SELECT * FROM tg_accounts WHERE status = 'active'").fetchall()
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


# ============================================================
# TELETHON SEND
# ============================================================

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

        # Simulate typing delay
        typing_time = get_typing_delay(len(text))
        await asyncio.sleep(min(typing_time, 5))  # Cap at 5s for speed

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


# ============================================================
# CAMPAIGN RUNNER (WITH FULL ANTI-SPAM)
# ============================================================

async def run_campaign(campaign_id):
    """
    Run campaign with full anti-spam protection:
    - Spintax for message uniqueness
    - Smart delays based on account age
    - Daily limits per account
    - First message safety check
    - Flood handling with account rotation
    - Sending window (9:00-22:00)
    """
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

    # Update campaign status
    conn = get_db()
    conn.execute(
        "UPDATE campaigns SET status = 'running', started_at = ?, total_contacts = ? WHERE id = ?",
        (datetime.now().isoformat(), len(contacts), campaign_id)
    )
    conn.commit()
    conn.close()

    results = {"sent": 0, "failed": 0, "skipped": 0, "errors": []}
    account_index = 0
    flood_until = {}  # account_id -> timestamp
    messages_per_account = campaign.get("messages_per_account", 20)
    messages_on_current = 0

    for contact in contacts:
        # Check campaign status
        conn = get_db()
        c = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        conn.close()
        if not c or c["status"] != "running":
            break

        # Check sending window (9-22)
        current_hour = datetime.now().hour
        if current_hour < 9 or current_hour >= 22:
            # Sleep until sending window
            sleep_hours = (9 - current_hour) % 24
            await asyncio.sleep(min(sleep_hours * 3600, 3600))  # Max 1 hour sleep
            continue

        username = contact["username"]
        contact_name = contact.get("name", "")
        is_first = is_first_contact(username)

        # Generate unique text with spintax
        template = random.choice(templates_to_use)
        text = generate_unique_text(template["text"], contact_name, username)

        # First message safety check
        if is_first:
            safe, reason = check_first_message(text)
            if not safe:
                results["skipped"] += 1
                results["errors"].append(f"{username}: {reason}")
                log_message(campaign_id, 0, username, "skipped", reason)
                continue

        # Try each account
        sent_ok = False
        attempts = 0
        max_attempts = len(accounts)

        while not sent_ok and attempts < max_attempts:
            # Find available (non-flooded, within daily limit) accounts
            available = []
            for a in accounts:
                if flood_until.get(a["id"], 0) > time.time():
                    continue
                age = get_account_age_days(a.get("created_at", ""))
                limit = get_daily_limit(age)
                sent_today = get_messages_today(a["id"])
                if sent_today < limit:
                    available.append(a)

            if not available:
                # All accounts exhausted - wait
                if flood_until:
                    min_wait = min(flood_until.values()) - time.time()
                    if min_wait > 0:
                        await asyncio.sleep(min(min_wait + 5, 300))
                    flood_until.clear()
                available = accounts

            account = available[account_index % len(available)]

            # Rotate if needed
            if messages_on_current >= messages_per_account:
                account_index = (account_index + 1) % len(available)
                messages_on_current = 0
                account = available[account_index % len(available)]

            # Send
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
                flood_until[account["id"]] = time.time() + flood_seconds
                log_message(campaign_id, account["id"], username, "flood_wait", error)
                account_index = (account_index + 1) % len(accounts)
                messages_on_current = 0
                attempts += 1

            else:
                results["failed"] += 1
                results["errors"].append(f"{username}: {error}")
                log_message(campaign_id, account["id"], username, "failed", error)
                attempts += 1

        update_campaign_progress(campaign_id)

        # Smart delay between successful sends
        if sent_ok:
            age = get_account_age_days(account.get("created_at", ""))
            sent_today = get_messages_today(account["id"])
            delay = get_smart_delay(age, sent_today, is_first)
            
            # Check for random long pause (lunch/break)
            hour = datetime.now().hour
            if 12 <= hour <= 14 and random.random() < 0.3:
                delay += random.uniform(1800, 3600)  # Lunch break
            
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
        loop.run_until_complete(send_single_test(account_phone, target_username, text))
        loop.close()

    import threading
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return True
