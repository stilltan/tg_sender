import asyncio
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
import os

SESSIONS_DIR = "/opt/tg_sender/sessions"
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

PROXIES = [
    ("rknzaebal.leeroy.uz", 443, "ee8d91a005d06a13c75649b62299de46ba726b6e7069646f72692e6c6565726f792e757a"),
    ("ccc.horizon555.co.uk", 8443, "eeNEgYdJvXrFGRMCIMJdCQ"),
    ("94.130.191.53", 8443, "dd104462821249bd7ac519130220c25d09"),
    ("87.232.123.234", 443, "ee339c0b8c4bd3d7ff26414d6fb6d6a7027477697463682e7476"),
    ("benz.cras.co.im", 144, "ee1603010200010001fc030386e24c3add626973636F7474692E79656B74616E65742E636F6D"),
]

async def try_one(host, port, secret, sp):
    try:
        client = TelegramClient(
            sp, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=(host, port, secret),
            connection_retries=0, timeout=8, retry_delay=0,
        )
        await asyncio.wait_for(client.connect(), timeout=8)
        if await client.is_user_authorized():
            me = await client.get_me()
            await client.disconnect()
            return True, f"{me.first_name}"
        await client.disconnect()
        return False, "no auth"
    except Exception as e:
        try: await client.disconnect()
        except: pass
        return False, str(e)[:40]

async def main():
    sessions = sorted([f.replace(".session","") for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")])
    phone = sessions[0]
    sp = os.path.join(SESSIONS_DIR, phone)
    print(f"Account: +{phone}, testing {len(PROXIES)} proxies in parallel...")

    tasks = [try_one(h, p, s, sp) for h, p, s in PROXIES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, (h, p, s) in enumerate(PROXIES):
        r = results[i]
        if isinstance(r, Exception):
            print(f"  {h}:{p} => ERR {str(r)[:30]}")
        else:
            ok, msg = r
            tag = "OK" if ok else "FAIL"
            print(f"  {h}:{p} => {tag} | {msg}")
            if ok:
                with open("/opt/tg_sender/proxy.conf", "w") as f:
                    f.write(f"{h}:{p}:{s}")
                print("  ==> SAVED!")

asyncio.run(main())
