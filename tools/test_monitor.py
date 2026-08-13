import asyncio
import sys
sys.path.insert(0, '/opt/tg_sender/web')
from tg_monitor import get_recent_chats

async def test():
    chats = await get_recent_chats('+919085691621', limit=10)
    print(f'Got {len(chats)} chats')
    for c in chats[:5]:
        if 'error' in c:
            print(f'  ERROR: {c["error"]}')
        else:
            name = c.get('name', '?')
            username = c.get('username', '?')
            unread = c.get('unread', 0)
            print(f'  {name} @{username} unread:{unread}')

asyncio.run(test())
