import asyncio
from telethon import TelegramClient
import os

SESSIONS_DIR = '/opt/tg_sender/sessions'
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'

# Попробуем через Telegram MTProto прокси (публичные)
# Формат: (host, port, secret)
MTPROXY_LIST = [
    ('158.160.6.22', 443, '1f3d04e5c1c0ca39cf42e98e49a3fa25'),
]

async def try_connect(phone, session_path, proxy_conf=None):
    try:
        proxy = None
        if proxy_conf:
            proxy = {'proxy_type': 'mtproxy', 'addr': proxy_conf[0], 'port': proxy_conf[1], 'secret': proxy_conf[2]}
        
        client = TelegramClient(session_path, API_ID, API_HASH, proxy=proxy, connection_retries=1, timeout=10)
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            await client.disconnect()
            return True, f'{me.first_name}'
        await client.disconnect()
        return False, 'not auth'
    except Exception as e:
        try: await client.disconnect()
        except: pass
        return False, str(e)[:40]

async def main():
    sessions = sorted([f.replace('.session','') for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
    phone = sessions[0]
    sp = os.path.join(SESSIONS_DIR, phone)
    
    print(f'Testing +{phone}...')
    print()
    
    # Direct
    print('Direct: ', end='', flush=True)
    ok, msg = await try_connect(phone, sp)
    print(f'{OK if ok else FAIL} | {msg}')
    
    # MTProto proxy
    for px in MTPROXY_LIST:
        print(f'MTProxy {px[0]}:{px[1]}: ', end='', flush=True)
        ok, msg = await try_connect(phone, sp, px)
        print(f'{OK if ok else FAIL} | {msg}')

asyncio.run(main())
