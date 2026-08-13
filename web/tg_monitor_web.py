#!/usr/bin/env python3
"""
Simple Telegram monitor - shows account chats in terminal style
Can be accessed via web at port 8080
"""
import asyncio
import sys
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from datetime import datetime

sys.path.insert(0, '/opt/tg_sender/web')
sys.path.insert(0, '/opt/tg_sender')

from tg_monitor import get_recent_chats, get_chat_messages, send_reply, get_account_info

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TG Monitor - {phone}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0e1621; color:#fff; font-family:'Segoe UI',sans-serif; }}
.header {{ background:#17212b; padding:16px 20px; border-bottom:1px solid #2b3a4a; display:flex; align-items:center; gap:12px; }}
.header h2 {{ font-size:18px; }}
.header .back {{ color:#6ab3f3; text-decoration:none; font-size:14px; }}
.chat-list {{ padding:8px; }}
.chat-item {{ display:flex; align-items:center; gap:12px; padding:12px 16px; border-radius:12px; cursor:pointer; transition:background 0.2s; }}
.chat-item:hover {{ background:#1e2c3a; }}
.avatar {{ width:48px; height:48px; border-radius:50%; background:#2b5278; display:flex; align-items:center; justify-content:center; font-size:18px; font-weight:700; color:#fff; flex-shrink:0; }}
.chat-info {{ flex:1; min-width:0; }}
.chat-name {{ font-weight:600; font-size:15px; }}
.chat-msg {{ color:#8b9bab; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.chat-time {{ color:#6d7f8f; font-size:11px; flex-shrink:0; }}
.badge {{ background:#5ca06a; color:#fff; border-radius:12px; padding:2px 8px; font-size:11px; font-weight:700; }}
.messages {{ max-height:70vh; overflow-y:auto; padding:16px; }}
.msg {{ max-width:70%; margin-bottom:8px; padding:10px 14px; border-radius:12px; font-size:14px; line-height:1.4; }}
.msg.sent {{ background:#2b5278; margin-left:auto; border-bottom-right-radius:4px; }}
.msg.received {{ background:#182533; border-bottom-left-radius:4px; }}
.msg .time {{ font-size:10px; color:#6d7f8f; margin-top:4px; }}
.reply-box {{ display:flex; gap:8px; padding:12px 16px; background:#17212b; border-top:1px solid #2b3a4a; }}
.reply-box input {{ flex:1; background:#242f3d; border:none; border-radius:20px; padding:10px 16px; color:#fff; font-size:14px; outline:none; }}
.reply-box button {{ background:#5ca06a; border:none; border-radius:50%; width:40px; height:40px; color:#fff; cursor:pointer; font-size:18px; }}
.title {{ text-align:center; padding:40px; color:#8b9bab; }}
a {{ color:#6ab3f3; }}
</style>
</head>
<body>
<div class="header">
    <a class="back" href="/">← Назад</a>
    <h2>👁 {phone}</h2>
</div>
{content}
</body>
</html>"""

HOME_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TG Monitor</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0e1621; color:#fff; font-family:'Segoe UI',sans-serif; }}
.header {{ background:#17212b; padding:20px; text-align:center; border-bottom:1px solid #2b3a4a; }}
.header h1 {{ font-size:24px; margin-bottom:4px; }}
.header p {{ color:#8b9bab; font-size:13px; }}
.accounts {{ padding:20px; display:grid; gap:16px; max-width:500px; margin:0 auto; }}
.account {{ background:#17212b; border-radius:16px; padding:20px; display:flex; align-items:center; gap:16px; cursor:pointer; transition:all 0.2s; border:1px solid #2b3a4a; }}
.account:hover {{ border-color:#5ca06a; transform:translateY(-2px); }}
.account .icon {{ width:56px; height:56px; border-radius:50%; background:linear-gradient(135deg,#5ca06a,#2b5278); display:flex; align-items:center; justify-content:center; font-size:24px; }}
.account .info h3 {{ font-size:16px; margin-bottom:4px; }}
.account .info p {{ color:#8b9bab; font-size:13px; }}
</style>
</head>
<body>
<div class="header">
    <h1>👁 TG Monitor</h1>
    <p>Выберите аккаунт для просмотра</p>
</div>
<div class="accounts">
{accounts}
</div>
</body>
</html>"""

ACCOUNTS = [
    {"phone": "+919084101190", "name": "I_Match_Oksana"},
    {"phone": "+919085691621", "name": "I_Match_OKSANA"},
    {"phone": "+919087271255", "name": "I_Match_Oksana gart"},
]


class MonitorHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            accounts_html = ""
            for acc in ACCOUNTS:
                accounts_html += f"""
                <a class="account" href="/chat/{acc['phone']}">
                    <div class="icon">👤</div>
                    <div class="info">
                        <h3>{acc['name']}</h3>
                        <p>{acc['phone']}</p>
                    </div>
                </a>
                """
            
            html = HOME_HTML.format(accounts=accounts_html)
            self.wfile.write(html.encode())
            
        elif self.path.startswith("/chat/"):
            phone = self.path.split("/chat/")[1].split("?")[0]
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            try:
                loop = asyncio.new_event_loop()
                chats = loop.run_until_complete(get_recent_chats(phone, limit=30))
                loop.close()
                
                chat_list = '<div class="chat-list">'
                for c in chats:
                    if "error" in c:
                        continue
                    name = c.get("name", "?")
                    username = c.get("username", "")
                    last = c.get("last_message", "")[:50]
                    unread = c.get("unread", 0)
                    initial = name[0].upper() if name else "?"
                    
                    badge = f'<span class="badge">{unread}</span>' if unread > 0 else ""
                    
                    chat_list += f"""
                    <a class="chat-item" href="/messages/{phone}/{username}" style="text-decoration:none;color:inherit">
                        <div class="avatar">{initial}</div>
                        <div class="chat-info">
                            <div class="chat-name">{name} {badge}</div>
                            <div class="chat-msg">@{username} · {last}</div>
                        </div>
                    </a>
                    """
                chat_list += "</div>"
                
                html = HTML_TEMPLATE.format(phone=phone, content=chat_list)
            except Exception as e:
                html = HTML_TEMPLATE.format(phone=phone, content=f'<div class="title">Ошибка: {str(e)[:100]}</div>')
            
            self.wfile.write(html.encode())
            
        elif self.path.startswith("/messages/"):
            parts = self.path.split("/")
            phone = parts[2]
            username = parts[3].split("?")[0]
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            try:
                loop = asyncio.new_event_loop()
                messages = loop.run_until_complete(get_chat_messages(phone, username, limit=50))
                loop.close()
                
                msg_html = f'<div class="header" style="padding:12px 16px"><a class="back" href="/chat/{phone}">← Назад</a><h2 style="font-size:16px">@{username}</h2></div>'
                msg_html += '<div class="messages" id="msgs">'
                
                for m in messages:
                    if "error" in m:
                        msg_html += f'<div class="title">{m["error"]}</div>'
                        continue
                    cls = "sent" if m.get("out") else "received"
                    time_str = m.get("date", "")[-8:-3] if m.get("date") else ""
                    text = m.get("text", "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    msg_html += f'<div class="msg {cls}">{text}<div class="time">{time_str}</div></div>'
                
                msg_html += '</div>'
                msg_html += f'''
                <form class="reply-box" method="POST" action="/send/{phone}/{username}">
                    <input type="text" name="message" placeholder="Введите сообщение..." autocomplete="off" required>
                    <button type="submit">➤</button>
                </form>
                <script>document.getElementById("msgs").scrollTop=999999;</script>
                '''
                
                html = HTML_TEMPLATE.format(phone=f"{phone} → @{username}", content=msg_html)
            except Exception as e:
                html = HTML_TEMPLATE.format(phone=phone, content=f'<div class="title">Ошибка: {str(e)[:100]}</div>')
            
            self.wfile.write(html.encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path.startswith("/send/"):
            parts = self.path.split("/")
            phone = parts[2]
            username = parts[3]
            
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            message = body.split("message=")[1] if "message=" in body else ""
            message = message.replace("+", " ").replace("%0A", "\n")
            
            if message:
                loop = asyncio.new_event_loop()
                ok, err = loop.run_until_complete(send_reply(phone, username, message))
                loop.close()
            
            self.send_response(302)
            self.send_header("Location", f"/messages/{phone}/{username}")
            self.end_headers()


if __name__ == "__main__":
    port = 8080
    server = HTTPServer(("0.0.0.0", port), MonitorHandler)
    print(f"TG Monitor running on http://0.0.0.0:{port}")
    server.serve_forever()
