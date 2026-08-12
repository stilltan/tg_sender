import asyncio
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
import os, json

SESSIONS_DIR = "/opt/tg_sender/sessions"
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
PROXY_HOST = "94.130.191.53"
PROXY_PORT = 8443
PROXY_SECRET = "dd104462821249bd7ac519130220c25d09"

async def main():
    sessions = sorted([f.replace(".session","") for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")])
    print(f"Testing {len(sessions)} accounts via proxy {PROXY_HOST}:{PROXY_PORT}")
    print()

    results = []
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
                uname = f"@{me.username}" if me.username else "no username"
                print(f"OK | {me.first_name} {me.last_name or ''} {uname}")
                results.append({"phone": phone, "name": f"{me.first_name} {me.last_name or ''}".strip(), "username": me.username, "status": "active"})
            else:
                print("NOT AUTHORIZED")
                results.append({"phone": phone, "status": "inactive"})
            await client.disconnect()
        except Exception as e:
            print(f"FAIL | {str(e)[:40]}")
            results.append({"phone": phone, "status": "error"})
            try: await client.disconnect()
            except: pass

    # Save results
    with open("/opt/tg_sender/accounts/account_status.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print()
    print(f"OK: {sum(1 for r in results if r['status']=='active')}/{len(results)}")
    print("Saved to account_status.json")

asyncio.run(main())
