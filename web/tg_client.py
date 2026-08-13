"""
TG Web Client — Full Telegram client via Telethon sessions
Works like Telegram Web but uses server-side sessions
"""
import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.tl.types import User as TgUser, Chat, Channel

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


async def get_client(phone: str):
    """Get connected Telethon client for a phone."""
    host, port, secret = get_proxy()
    session_path = str(SESSIONS_DIR / phone.replace("+", ""))
    
    proxy = None
    if host:
        proxy = (host, port, secret)
    
    client = TelegramClient(
        session_path, API_ID, API_HASH,
        connection=ConnectionTcpMTProxyRandomizedIntermediate,
        proxy=proxy, connection_retries=2, timeout=20,
    )
    await asyncio.wait_for(client.connect(), timeout=20)
    return client


async def get_account_info(phone: str) -> dict:
    """Get account profile info."""
    try:
        client = await get_client(phone)
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        
        me = await client.get_me()
        await client.disconnect()
        
        return {
            "id": me.id,
            "phone": phone,
            "username": me.username or "",
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "premium": getattr(me, "premium", False) or False,
        }
    except Exception as e:
        return None


async def get_dialogs(phone: str, limit: int = 50) -> list:
    """Get dialogs (chats) for an account."""
    try:
        client = await get_client(phone)
        if not await client.is_user_authorized():
            await client.disconnect()
            return []
        
        me = await client.get_me()
        dialogs = []
        
        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            
            # Get peer info
            peer_type = "user"
            peer_id = entity.id
            name = ""
            username = ""
            photo = None
            
            if isinstance(entity, TgUser):
                peer_type = "user"
                name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                username = entity.username or ""
                if entity.photo:
                    photo = f"https://t.me/{username}" if username else None
            elif isinstance(entity, (Chat, Channel)):
                peer_type = "channel" if isinstance(entity, Channel) else "group"
                name = entity.title or ""
                username = getattr(entity, "username", "") or ""
            
            # Last message info
            last_msg_text = ""
            last_msg_date = ""
            last_msg_out = False
            if dialog.message:
                last_msg_text = (dialog.message.text or "[медиа]")[:100]
                last_msg_date = dialog.message.date.isoformat() if dialog.message.date else ""
                last_msg_out = dialog.message.out
            
            dialogs.append({
                "id": peer_id,
                "type": peer_type,
                "name": name or username or str(peer_id),
                "username": username,
                "last_message": last_msg_text,
                "last_date": last_msg_date,
                "last_out": last_msg_out,
                "unread": dialog.unread_count,
                "pinned": dialog.pinned,
            })
        
        await client.disconnect()
        return dialogs
        
    except Exception as e:
        return [{"error": str(e)[:80]}]


async def get_messages(phone: str, peer_id: int, peer_type: str = "user", limit: int = 50) -> list:
    """Get messages from a chat."""
    try:
        client = await get_client(phone)
        if not await client.is_user_authorized():
            await client.disconnect()
            return []
        
        # Get entity
        try:
            if peer_type == "user":
                entity = await client.get_entity(peer_id)
            else:
                entity = await client.get_entity(peer_id)
        except Exception:
            await client.disconnect()
            return [{"error": "Чат не найден"}]
        
        messages = []
        async for msg in client.iter_messages(entity, limit=limit):
            msg_data = {
                "id": msg.id,
                "text": msg.text or "",
                "date": msg.date.isoformat() if msg.date else "",
                "out": msg.out,
                "media": None,
            }
            
            # Check for media
            if msg.photo:
                msg_data["media"] = "📷 Фото"
            elif msg.document:
                msg_data["media"] = "📎 Файл"
            elif msg.sticker:
                msg_data["media"] = "🎨 Стикер"
            elif msg.voice:
                msg_data["media"] = "🎤 Голосовое"
            
            messages.append(msg_data)
        
        await client.disconnect()
        messages.reverse()
        return messages
        
    except Exception as e:
        return [{"error": str(e)[:80]}]


async def send_message(phone: str, peer_id: int, text: str) -> tuple:
    """Send a message from an account."""
    try:
        client = await get_client(phone)
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Not authorized"
        
        entity = await client.get_entity(peer_id)
        await client.send_message(entity, text)
        await client.disconnect()
        return True, "Sent"
        
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, str(e)[:80]


async def mark_read(phone: str, peer_id: int) -> bool:
    """Mark messages as read."""
    try:
        client = await get_client(phone)
        if not await client.is_user_authorized():
            await client.disconnect()
            return False
        
        entity = await client.get_entity(peer_id)
        await client.send_read_acknowledge(entity)
        await client.disconnect()
        return True
    except Exception:
        try:
            await client.disconnect()
        except:
            pass
        return False


def get_available_accounts() -> list:
    """Get list of available session files."""
    if not SESSIONS_DIR.exists():
        return []
    
    accounts = []
    for f in sorted(SESSIONS_DIR.iterdir()):
        if f.suffix == ".session":
            phone = f"+{f.stem}"
            accounts.append(phone)
    return accounts
