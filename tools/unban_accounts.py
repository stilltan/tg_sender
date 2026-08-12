"""
Auto-unban: appeals spam blocks via @SpamBot
"""
import asyncio
import time
from telethon import TelegramClient, events
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.tl.types import KeyboardButtonCallback
import os

SESSIONS_DIR = "/opt/tg_sender/sessions"
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
PROXY_HOST = "94.130.191.53"
PROXY_PORT = 8443
PROXY_SECRET = "dd104462821249bd7ac519130220c25d09"

SPAM_BOT = "SpamBot"

APPEAL_TEXT = (
    "Telegram developers! I have not used telegram for a long time, "
    "and have not written in various public groups. "
    "You restricted my account by mistake. "
    "I think this is wrong because I did not violate any rules. "
    "Therefore I ask you to please remove the restrictions from my account. "
    "Thank you!"
)


async def unban_account(phone):
    """Try to unban a single account via @SpamBot."""
    sp = os.path.join(SESSIONS_DIR, phone)
    
    try:
        client = TelegramClient(
            sp, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=(PROXY_HOST, PROXY_PORT, PROXY_SECRET),
            connection_retries=2, timeout=20,
        )
        await asyncio.wait_for(client.connect(), timeout=20)
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Not authorized"
        
        me = await client.get_me()
        print(f"  Connected as {me.first_name}")
        
        # Step 1: Send /start to @SpamBot
        print(f"  Step 1: Sending /start to @{SPAM_BOT}...")
        await client.send_message(SPAM_BOT, "/start")
        await asyncio.sleep(3)
        
        # Step 2: Read the response and click buttons
        print(f"  Step 2: Reading response...")
        messages = await client.get_messages(SPAM_BOT, limit=5)
        
        if not messages:
            await client.disconnect()
            return False, "No response from SpamBot"
        
        # Check current status from the latest message
        latest = messages[0]
        text = latest.text or ""
        print(f"  SpamBot says: {text[:100]}...")
        
        # If already free
        if "free" in text.lower() or "свободен" in text.lower() or "no restrictions" in text.lower():
            await client.disconnect()
            return True, "Account is already free!"
        
        # Step 3: Try to click inline buttons
        if latest.reply_markup and latest.reply_markup.rows:
            buttons = []
            for row in latest.reply_markup.rows:
                for btn in row.buttons:
                    if hasattr(btn, 'text'):
                        buttons.append(btn.text)
            
            print(f"  Available buttons: {buttons}")
            
            # Look for "This is a mistake" / "Это ошибка"
            mistake_btn = None
            for row in latest.reply_markup.rows:
                for btn in row.buttons:
                    if hasattr(btn, 'text'):
                        btn_text = btn.text.lower()
                        if "mistake" in btn_text or "ошибк" in btn_text or "error" in btn_text:
                            mistake_btn = btn
                            break
            
            if mistake_btn:
                print(f"  Step 3: Clicking '{mistake_btn.text}'...")
                await latest.click(text=mistake_btn.text)
                await asyncio.sleep(3)
                
                # Get new response
                messages2 = await client.get_messages(SPAM_BOT, limit=3)
                if messages2:
                    latest2 = messages2[0]
                    text2 = latest2.text or ""
                    print(f"  SpamBot says: {text2[:100]}...")
                    
                    # Look for "Yes" / "Да" button
                    if latest2.reply_markup and latest2.reply_markup.rows:
                        yes_btn = None
                        for row in latest2.reply_markup.rows:
                            for btn in row.buttons:
                                if hasattr(btn, 'text'):
                                    btn_text = btn.text.lower()
                                    if btn_text in ["yes", "да"]:
                                        yes_btn = btn
                                        break
                        
                        if yes_btn:
                            print(f"  Step 4: Clicking '{yes_btn.text}'...")
                            await latest2.click(text=yes_btn.text)
                            await asyncio.sleep(3)
                            
                            # Get new response
                            messages3 = await client.get_messages(SPAM_BOT, limit=3)
                            if messages3:
                                latest3 = messages3[0]
                                text3 = latest3.text or ""
                                print(f"  SpamBot says: {text3[:100]}...")
                                
                                # Look for "No, nothing" / "Нет, ничего"
                                if latest3.reply_markup and latest3.reply_markup.rows:
                                    no_btn = None
                                    for row in latest3.reply_markup.rows:
                                        for btn in row.buttons:
                                            if hasattr(btn, 'text'):
                                                btn_text = btn.text.lower()
                                                if "нет" in btn_text or "no" in btn_text or "nothing" in btn_text:
                                                    no_btn = btn
                                                    break
                                    
                                    if no_btn:
                                        print(f"  Step 5: Clicking '{no_btn.text}'...")
                                        await latest3.click(text=no_btn.text)
                                        await asyncio.sleep(3)
                                    
                                    # Step 6: Send appeal text
                                    print(f"  Step 6: Sending appeal text...")
                                    await client.send_message(SPAM_BOT, APPEAL_TEXT)
                                    await asyncio.sleep(3)
                                    
                                    # Get final response
                                    messages4 = await client.get_messages(SPAM_BOT, limit=3)
                                    if messages4:
                                        final_text = messages4[0].text or ""
                                        print(f"  Final: {final_text[:150]}...")
                                    
                                    await client.disconnect()
                                    return True, "Appeal sent! Check status in 24h"
        
        # If no buttons or different flow - just send appeal directly
        print(f"  Sending appeal directly...")
        await client.send_message(SPAM_BOT, APPEAL_TEXT)
        await asyncio.sleep(3)
        
        messages5 = await client.get_messages(SPAM_BOT, limit=3)
        if messages5:
            final = messages5[0].text or ""
            print(f"  Response: {final[:150]}...")
        
        await client.disconnect()
        return True, "Appeal sent directly"
        
    except Exception as e:
        try:
            await client.disconnect()
        except:
            pass
        return False, str(e)[:80]


async def main():
    sessions = sorted([f.replace('.session', '') for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
    print(f"=== SpamBot Appeal for {len(sessions)} accounts ===")
    print()
    
    results = []
    for phone in sessions:
        print(f"+{phone}:")
        ok, msg = await unban_account(phone)
        status = "OK" if ok else "FAIL"
        print(f"  Result: {status} | {msg}")
        results.append({"phone": phone, "ok": ok, "msg": msg})
        print()
        
        # Delay between accounts
        await asyncio.sleep(5)
    
    print("=== Summary ===")
    for r in results:
        tag = "OK" if r["ok"] else "FAIL"
        print(f"  +{r['phone']}: {tag} | {r['msg']}")


if __name__ == "__main__":
    asyncio.run(main())
