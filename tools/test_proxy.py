import asyncio
from telethon import TelegramClient
import os

SESSIONS_DIR = '/opt/tg_sender/sessions'
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'

async def test_account(phone, session_path, use_proxy=False):
    try:
        proxy = None
        if use_proxy:
            proxy = ('mtproxy', '158.160.6.22', 443, '1f3d04e5c1c0ca39cf42e98e49a3fa25')
            proxy = {'proxy_type': 'mtproxy', 'addr': '158.160.6.22', 'port': 443, 'secret': '1f3d04e5c1c0ca39cf42e98e49a3fa25'}
        
        client = TelegramClient(session_path, API_ID, API_HASH, proxy=proxy, connection_retries=2, timeout=15)
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            await client.disconnect()
            return True, f'{me.first_name} (@{me.username or "n/a"})'
        else:
            await client.disconnect()
            return False, 'not authorized'
    except Exception as e:
        try: await client.disconnect()
        except: pass
        return False, str(e)[:60]

async def main():
    sessions = sorted([f.replace('.session','') for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
    print(f'Accounts: {len(sessions)}')
    
    print()
    print('--- Direct (no proxy) ---')
    phone = sessions[0]
    ok, msg = await test_account(phone, os.path.join(SESSIONS_DIR, phone), False)
    print(f'  +{phone}: {"OK" if ok else "FAIL"} | {msg}')
    
    print()
    print('--- Via MTProto proxy ---')
    for phone in sessions:
        ok, msg = await test_account(phone, os.path.join(SESSIONS_DIR, phone), True)
        print(f'  +{phone}: {"OK" if ok else "FAIL"} | {msg}')

asyncio.run(main())
