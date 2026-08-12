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
TARGET = "Cursdworld"

async def main():
    sessions = sorted([f.replace('.session', '') for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
    print(f"Sending test to @{TARGET} from {len(sessions)} accounts...")
    print()

    for phone in sessions:
        sp = os.path.join(SESSIONS_DIR, phone)
        print(f"+{phone}: ", end="", flush=True)
        try:
            client = TelegramClient(
                sp, API_ID, API_HASH,
                connection=ConnectionTcpMTProxyRandomizedIntermediate,
                proxy=(PROXY_HOST, PROXY_PORT, PROXY_SECRET),
                connection_retries=1, timeout=15,
            )
            await asyncio.wait_for(client.connect(), timeout=15)
            if await client.is_user_authorized():
                me = await client.get_me()
                await client.send_message(TARGET, f"Test from +{phone} ({me.first_name}) - TG Sender OK!")
                print(f"OK | sent to @{TARGET}")
            else:
                print("NOT AUTHORIZED")
            await client.disconnect()
        except Exception as e:
            print(f"FAIL | {str(e)[:50]}")
            try: await client.disconnect()
            except: pass

asyncio.run(main())
