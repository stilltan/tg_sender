"""
Check ban status for all accounts via @SpamBot
"""
import asyncio
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
import os

SESSIONS_DIR = "/opt/tg_sender/sessions"
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
PROXY_HOST = "94.130.191.53"
PROXY_PORT = 8443
PROXY_SECRET = "dd104462821249bd7ac519130220c25d09"


async def check_account(phone):
    sp = os.path.join(SESSIONS_DIR, phone)
    try:
        client = TelegramClient(
            sp, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=(PROXY_HOST, PROXY_PORT, PROXY_SECRET),
            connection_retries=1, timeout=15,
        )
        await asyncio.wait_for(client.connect(), timeout=15)
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return "NOT_AUTH", "Not authorized"
        
        await client.send_message("SpamBot", "/start")
        await asyncio.sleep(3)
        
        messages = await client.get_messages("SpamBot", limit=3)
        await client.disconnect()
        
        if not messages:
            return "NO_RESPONSE", "No response"
        
        text = (messages[0].text or "").lower()
        
        if "free" in text or "свободен" in text or "no restrictions" in text or "нет ограничений" in text:
            return "FREE", "No restrictions"
        elif "limited" in text or "ограничен" in text or "restricted" in text or "spam" in text:
            return "BANNED", "Restricted"
        else:
            return "UNKNOWN", text[:80]
    except Exception as e:
        return "ERROR", str(e)[:60]


async def main():
    sessions = sorted([f.replace('.session', '') for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
    print(f"Checking {len(sessions)} accounts...")
    print()
    
    for phone in sessions:
        status, msg = await check_account(phone)
        icon = {"FREE": "OK", "BANNED": "XX", "NOT_AUTH": "--", "ERROR": "!!", "NO_RESPONSE": "??"}.get(status, "??")
        print(f"  [{icon}] +{phone}: {msg}")
        await asyncio.sleep(3)


asyncio.run(main())
