"""
TG Sender — Web Dashboard for Telegram Message Broadcasting
"""
from __future__ import annotations

import os
import sys
import json
import asyncio
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Add parent directory to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ============================================================
# APP SETUP
# ============================================================

app = FastAPI(title="TG Sender", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))

templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ============================================================
# DATABASE
# ============================================================

DB_PATH = ROOT / "data" / "sender.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tg_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone TEXT NOT NULL,
            api_id INTEGER,
            api_hash TEXT,
            session_string TEXT,
            status TEXT DEFAULT 'inactive',
            last_used TEXT,
            messages_sent INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            name TEXT,
            description TEXT,
            group_name TEXT DEFAULT 'default',
            status TEXT DEFAULT 'active',
            last_contacted TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS message_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_id INTEGER,
            contact_group TEXT DEFAULT 'all',
            status TEXT DEFAULT 'draft',
            delay_min INTEGER DEFAULT 30,
            delay_max INTEGER DEFAULT 60,
            messages_per_account INTEGER DEFAULT 20,
            total_contacts INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES message_templates(id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            account_id INTEGER,
            contact_id INTEGER,
            contact_username TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (account_id) REFERENCES tg_accounts(id)
        )
    """)
    
    # Миграция старой схемы БД (добавляет недостающие колонки)
    conn.close()
    migrate_db()
    conn = get_db()
    cur = conn.cursor()

    # Create default admin user
    existing = cur.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not existing:
        default_password = os.environ.get("TG_SENDER_ADMIN_PASSWORD", "admin123")
        default_hash = hashlib.sha256(default_password.encode()).hexdigest()
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", default_hash)
        )
    
    conn.commit()
    conn.close()


def migrate_db():
    """Добавляет недостающие колонки в уже существующую БД (без потери данных).

    SQLite не поддерживает ALTER TABLE ADD COLUMN IF NOT EXISTS,
    поэтому проверяем PRAGMA table_info и добавляем только то, чего нет.
    """
    conn = get_db()
    cur = conn.cursor()

    # (таблица, [(колонка, SQL-определение), ...])
    migrations = {
        "message_log": [
            ("account_id", "INTEGER"),
        ],
        "campaigns": [
            ("template_id", "INTEGER"),
            ("messages_per_account", "INTEGER DEFAULT 20"),
        ],
    }
    for table, cols in migrations.items():
        existing = {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, ddl in cols:
            if col not in existing:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

    conn.commit()
    conn.close()


# ============================================================
# AUTH HELPERS
# ============================================================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def get_current_user(request: Request) -> Optional[Dict]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def require_auth(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ============================================================
# ROUTES - AUTH
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    if user and verify_password(password, user["password_hash"]):
        request.session["user_id"] = user["id"]
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Неверный логин или пароль"
    })

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

# ============================================================
# ROUTES - DASHBOARD
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    
    # Stats
    total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    active_contacts = conn.execute("SELECT COUNT(*) FROM contacts WHERE status = 'active'").fetchone()[0]
    contacted = conn.execute("SELECT COUNT(*) FROM contacts WHERE status = 'contacted'").fetchone()[0]
    
    total_accounts = conn.execute("SELECT COUNT(*) FROM tg_accounts").fetchone()[0]
    active_accounts = conn.execute("SELECT COUNT(*) FROM tg_accounts WHERE status = 'active'").fetchone()[0]
    
    total_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
    running_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'running'").fetchone()[0]
    
    total_sent = conn.execute("SELECT COALESCE(SUM(sent_count), 0) FROM campaigns").fetchone()[0]
    
    # Recent campaigns
    campaigns = conn.execute(
        "SELECT * FROM campaigns ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    
    conn.close()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "stats": {
            "total_contacts": total_contacts,
            "active_contacts": active_contacts,
            "contacted": contacted,
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "total_campaigns": total_campaigns,
            "running_campaigns": running_campaigns,
            "total_sent": total_sent,
        },
        "campaigns": [dict(c) for c in campaigns],
    })

# ============================================================
# ROUTES - ACCOUNTS
# ============================================================

@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    accounts = conn.execute("SELECT * FROM tg_accounts ORDER BY created_at DESC").fetchall()
    conn.close()
    
    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "user": user,
        "accounts": [dict(a) for a in accounts],
    })

@app.post("/accounts/add")
async def add_account(request: Request, phone: str = Form(...), api_id: int = Form(...), api_hash: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    conn.execute(
        "INSERT INTO tg_accounts (user_id, phone, api_id, api_hash) VALUES (?, ?, ?, ?)",
        (user["id"], phone, api_id, api_hash)
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/accounts", status_code=302)

@app.post("/accounts/{account_id}/delete")
async def delete_account(request: Request, account_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    conn.execute("DELETE FROM tg_accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/accounts", status_code=302)


@app.post("/accounts/unban_all")
async def unban_all(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    import subprocess
    try:
        subprocess.Popen(
            ["bash", "-c", "cd /opt/tg_sender && source venv/bin/activate && python3 tools/unban_accounts.py > /opt/tg_sender/data/unban_log.txt 2>&1 &"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass
    
    return RedirectResponse(url="/accounts?unban=started", status_code=302)

@app.get("/api/accounts")
async def api_accounts(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    conn = get_db()
    accounts = conn.execute("SELECT id, phone, status, messages_sent, last_used FROM tg_accounts").fetchall()
    conn.close()
    
    return JSONResponse([dict(a) for a in accounts])

# ============================================================
# ROUTES - CONTACTS
# ============================================================

@app.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request, group: str = "all", page: int = 1):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    
    # Get groups
    groups = conn.execute("SELECT DISTINCT group_name FROM contacts ORDER BY group_name").fetchall()
    groups = [g["group_name"] for g in groups]
    
    # Get contacts
    per_page = 50
    offset = (page - 1) * per_page
    
    if group and group != "all":
        total = conn.execute("SELECT COUNT(*) FROM contacts WHERE group_name = ?", (group,)).fetchone()[0]
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE group_name = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (group, per_page, offset)
        ).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        contacts = conn.execute(
            "SELECT * FROM contacts ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        ).fetchall()
    
    total_pages = (total + per_page - 1) // per_page
    
    conn.close()
    
    return templates.TemplateResponse("contacts.html", {
        "request": request,
        "user": user,
        "contacts": [dict(c) for c in contacts],
        "groups": groups,
        "current_group": group,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })

@app.post("/contacts/add")
async def add_contact(request: Request, username: str = Form(...), name: str = Form(""), description: str = Form(""), group: str = Form("default")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Clean username
    username = username.strip().lstrip("@")
    if "t.me/" in username:
        username = username.split("t.me/")[-1]
    
    conn = get_db()
    conn.execute(
        "INSERT INTO contacts (username, name, description, group_name) VALUES (?, ?, ?, ?)",
        (username, name, description, group)
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/contacts", status_code=302)

@app.post("/contacts/import")
async def import_contacts(request: Request, contacts_text: str = Form(""), group: str = Form("imported")):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    added = 0
    
    for line in contacts_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        
        parts = [p.strip() for p in line.split("|")]
        username = parts[0].lstrip("@")
        if "t.me/" in username:
            username = username.split("t.me/")[-1]
        
        name = parts[1] if len(parts) > 1 else ""
        desc = parts[2] if len(parts) > 2 else ""
        
        if not username:
            continue
        
        # Check duplicate
        existing = conn.execute("SELECT id FROM contacts WHERE username = ?", (username,)).fetchone()
        if existing:
            continue
        
        conn.execute(
            "INSERT INTO contacts (username, name, description, group_name) VALUES (?, ?, ?, ?)",
            (username, name[:200], desc[:500], group)
        )
        added += 1
    
    conn.commit()
    conn.close()
    
    return RedirectResponse(url=f"/contacts?group={group}", status_code=302)

@app.post("/contacts/{contact_id}/status")
async def update_contact_status(request: Request, contact_id: int, status: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    conn = get_db()
    conn.execute(
        "UPDATE contacts SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), contact_id)
    )
    conn.commit()
    conn.close()
    
    return JSONResponse({"ok": True})

@app.post("/contacts/{contact_id}/delete")
async def delete_contact(request: Request, contact_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/contacts", status_code=302)

# ============================================================
# ROUTES - TEMPLATES
# ============================================================

@app.get("/templates", response_class=HTMLResponse)
async def templates_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    tmpls = conn.execute("SELECT * FROM message_templates ORDER BY created_at DESC").fetchall()
    conn.close()
    
    return templates.TemplateResponse("templates.html", {
        "request": request,
        "user": user,
        "templates": [dict(t) for t in tmpls],
    })

@app.post("/templates/add")
async def add_template(request: Request, name: str = Form(...), text: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    conn.execute("INSERT INTO message_templates (name, text) VALUES (?, ?)", (name, text))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/templates", status_code=302)

@app.post("/templates/{template_id}/delete")
async def delete_template(request: Request, template_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    conn.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/templates", status_code=302)

# ============================================================
# ROUTES - CAMPAIGNS
# ============================================================

@app.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    campaigns = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
    conn.close()
    
    return templates.TemplateResponse("campaigns.html", {
        "request": request,
        "user": user,
        "campaigns": [dict(c) for c in campaigns],
    })

@app.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    tmpls = conn.execute("SELECT * FROM message_templates").fetchall()
    groups = conn.execute("SELECT DISTINCT group_name FROM contacts").fetchall()
    conn.close()
    
    return templates.TemplateResponse("new_campaign.html", {
        "request": request,
        "user": user,
        "templates": [dict(t) for t in tmpls],
        "groups": [g["group_name"] for g in groups],
    })

@app.post("/campaigns/create")
async def create_campaign(
    request: Request,
    name: str = Form(...),
    template_id: int = Form(...),
    contact_group: str = Form("all"),
    delay_min: int = Form(30),
    delay_max: int = Form(60),
    messages_per_account: int = Form(20),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    conn.execute(
        """INSERT INTO campaigns (name, template_id, contact_group, delay_min, delay_max, messages_per_account)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, template_id, contact_group, delay_min, delay_max, messages_per_account)
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/campaigns", status_code=302)

@app.post("/campaigns/{campaign_id}/start")
async def start_campaign(request: Request, campaign_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    conn = get_db()
    conn.execute("UPDATE campaigns SET status = 'running', started_at = ? WHERE id = ?", 
                 (datetime.now().isoformat(), campaign_id))
    conn.commit()
    conn.close()
    
    # Start sending in background
    try:
        from sender_engine import start_campaign_async
        start_campaign_async(campaign_id)
    except Exception as e:
        print(f"Campaign start error: {e}")
    
    return JSONResponse({"ok": True, "message": "Рассылка запущена"})

@app.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(request: Request, campaign_id: int):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    conn = get_db()
    conn.execute("UPDATE campaigns SET status = 'paused' WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    
    return JSONResponse({"ok": True})

@app.post("/campaigns/{campaign_id}/delete")
async def delete_campaign(request: Request, campaign_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    conn.execute("DELETE FROM message_log WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/campaigns", status_code=302)

# ============================================================
# ROUTES - ANALYTICS
# ============================================================

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    
    # Daily stats for last 30 days
    daily_stats = []
    for i in range(30, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = conn.execute(
            "SELECT COUNT(*) FROM message_log WHERE date(sent_at) = ? AND status = 'sent'",
            (date,)
        ).fetchone()[0]
        daily_stats.append({"date": date, "sent": count})
    
    # Account performance
    accounts = conn.execute("""
        SELECT a.phone, a.messages_sent, a.status,
               (SELECT COUNT(*) FROM message_log ml WHERE ml.account_id = a.id AND ml.status = 'sent') as sent,
               (SELECT COUNT(*) FROM message_log ml WHERE ml.account_id = a.id AND ml.status = 'failed') as failed
        FROM tg_accounts a
    """).fetchall()
    
    conn.close()
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "user": user,
        "daily_stats": daily_stats,
        "accounts": [dict(a) for a in accounts],
    })

# ============================================================
# ROUTES - SETTINGS
# ============================================================

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    admins = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    accounts = conn.execute("SELECT * FROM tg_accounts WHERE status = 'active'").fetchall()
    conn.close()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "admins": [dict(a) for a in admins],
        "total_contacts": total_contacts,
        "accounts": [dict(a) for a in accounts],
    })


@app.post("/settings/add_user")
async def add_user(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return RedirectResponse(url="/settings", status_code=302)
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/delete_user/{user_id}")
async def delete_user(request: Request, user_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # Don't delete yourself
    if user["id"] == user_id:
        return RedirectResponse(url="/settings", status_code=302)
    
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/settings", status_code=302)


@app.post("/settings/test_send")
async def test_send(
    request: Request,
    account_phone: str = Form(...),
    target_username: str = Form(...),
    message_text: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    target_username = target_username.strip().lstrip("@")
    if "t.me/" in target_username:
        target_username = target_username.split("t.me/")[-1]
    
    try:
        from sender_engine import send_test_async
        send_test_async(account_phone, target_username, message_text)
    except Exception:
        pass
    
    return RedirectResponse(url="/settings?test=started", status_code=302)


@app.get("/export/contacts")
async def export_contacts(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    import csv
    import io
    conn = get_db()
    contacts = conn.execute("SELECT * FROM contacts ORDER BY group_name, username").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["username", "name", "description", "group_name", "status", "last_contacted"])
    for c in contacts:
        writer.writerow([c["username"], c["name"], c["description"], c["group_name"], c["status"], c["last_contacted"]])
    
    from starlette.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts_export.csv"}
    )

# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():
    init_db()
    print("✅ TG Sender Web started")
    print("📊 Dashboard: http://localhost:8000")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
