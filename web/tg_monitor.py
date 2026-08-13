"""
TG Account Monitor — view Telegram messages and reply from web
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate

ROOT = Path(__file__).resolve().parent.parent
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


async def get_recent_chats(phone: str, limit: int = 20):
    """Get recent chats/dialogs from an account."""
    host, port, secret = get_proxy()
    session_path = str(SESSIONS_DIR / phone.replace("+", ""))
    
    client = None
    try:
        proxy = None
        if host:
            proxy = (host, port, secret)
        
        client = TelegramClient(
            session_path, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy, connection_retries=1, timeout=15,
        )
        await asyncio.wait_for(client.connect(), timeout=20)
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return []
        
        me = await client.get_me()
        dialogs = []
        
        async for dialog in client.iter_dialogs(limit=limit):
            if dialog.is_user:  # Only private chats
                entity = dialog.entity
                username = getattr(entity, 'username', None)
                first_name = getattr(entity, 'first_name', '')
                last_name = getattr(entity, 'last_name', '')
                
                dialogs.append({
                    'id': entity.id,
                    'username': username or '',
                    'name': f"{first_name} {last_name}".strip() or username or str(entity.id),
                    'last_message': dialog.message.text[:100] if dialog.message else '',
                    'last_date': dialog.date.isoformat() if dialog.date else '',
                    'unread': dialog.unread_count,
                    'is_contact': entity.contact if hasattr(entity, 'contact') else False,
                })
        
        await client.disconnect()
        return dialogs
        
    except Exception as e:
        if client:
            try: await client.disconnect()
            except: pass
        return [{'error': str(e)[:80]}]


async def get_chat_messages(phone: str, username: str, limit: int = 30):
    """Get messages from a specific chat."""
    host, port, secret = get_proxy()
    session_path = str(SESSIONS_DIR / phone.replace("+", ""))
    
    client = None
    try:
        proxy = None
        if host:
            proxy = (host, port, secret)
        
        client = TelegramClient(
            session_path, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy, connection_retries=1, timeout=15,
        )
        await asyncio.wait_for(client.connect(), timeout=20)
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return []
        
        me = await client.get_me()
        
        try:
            entity = await client.get_entity(username)
        except Exception:
            await client.disconnect()
            return [{'error': f'User @{username} not found'}]
        
        messages = []
        async for msg in client.iter_messages(entity, limit=limit):
            messages.append({
                'id': msg.id,
                'text': msg.text or '[медиа]',
                'date': msg.date.isoformat(),
                'out': msg.out,  # True if sent by us
                'sender_name': 'Вы' if msg.out else (getattr(entity, 'first_name', '') or username),
            })
        
        await client.disconnect()
        messages.reverse()  # Oldest first
        return messages
        
    except Exception as e:
        if client:
            try: await client.disconnect()
            except: pass
        return [{'error': str(e)[:80]}]


async def send_reply(phone: str, username: str, text: str):
    """Send a reply to a user from an account."""
    host, port, secret = get_proxy()
    session_path = str(SESSIONS_DIR / phone.replace("+", ""))
    
    client = None
    try:
        proxy = None
        if host:
            proxy = (host, port, secret)
        
        client = TelegramClient(
            session_path, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy, connection_retries=1, timeout=15,
        )
        await asyncio.wait_for(client.connect(), timeout=20)
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Not authorized"
        
        try:
            entity = await client.get_entity(username)
            await client.send_message(entity, text)
            await client.disconnect()
            return True, "Sent"
        except Exception as e:
            await client.disconnect()
            return False, str(e)[:80]
        
    except Exception as e:
        if client:
            try: await client.disconnect()
            except: pass
        return False, str(e)[:80]


async def get_account_info(phone: str):
    """Get account info."""
    host, port, secret = get_proxy()
    session_path = str(SESSIONS_DIR / phone.replace("+", ""))
    
    client = None
    try:
        proxy = None
        if host:
            proxy = (host, port, secret)
        
        client = TelegramClient(
            session_path, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy, connection_retries=1, timeout=15,
        )
        await asyncio.wait_for(client.connect(), timeout=20)
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        
        me = await client.get_me()
        await client.disconnect()
        
        return {
            'id': me.id,
            'phone': phone,
            'username': me.username or '',
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'premium': me.premium or False,
        }
    except Exception as e:
        if client:
            try: await client.disconnect()
            except: pass
        return None
