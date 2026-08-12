#!/usr/bin/env python3
"""Import contacts from Google Sheets into tg_sender database."""
import sqlite3
import json
import re
import urllib.request

SHEET_URL = "https://docs.google.com/spreadsheets/d/1ndEkxU5g12iz5cLDuDyDUoT6cgoWAi9-/gviz/tq?tqx=out:csv&gid=1234938014"
DB_PATH = "/opt/tg_sender/data/sender.db"

def fetch_sheet():
    """Fetch CSV from Google Sheets."""
    url = SHEET_URL.replace("/edit", "").replace("#gid=", "&gid=")
    # Use the gviz JSON endpoint
    json_url = "https://docs.google.com/spreadsheets/d/1ndEkxU5g12iz5cLDuDyDUoT6cgoWAi9-/gviz/tq?tqx=out:json&gid=1234938014"
    
    req = urllib.request.Request(json_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode('utf-8')
    
    # Strip google.visualization.Query.setResponse(...) wrapper
    text = text.strip()
    if text.startswith("google.visualization.Query.setResponse("):
        text = text[len("google.visualization.Query.setResponse("):]
        if text.endswith(");"):
            text = text[:-2]
    
    data = json.loads(text)
    rows = data.get("table", {}).get("rows", [])
    
    contacts = []
    for row in rows:
        cells = row.get("c", [])
        if not cells or len(cells) < 3:
            continue
        
        # Extract cell values
        url_cell = cells[0].get("v", "") if cells[0] else ""
        name_cell = cells[1].get("v", "") if len(cells) > 1 and cells[1] else ""
        desc_cell = cells[2].get("v", "") if len(cells) > 2 and cells[2] else ""
        
        if not url_cell:
            continue
        
        # Clean username from URL
        username = str(url_cell).strip()
        if "t.me/" in username:
            username = username.split("t.me/")[-1]
        username = username.lstrip("@").strip()
        
        if not username:
            continue
        
        contacts.append({
            "username": username,
            "name": str(name_cell).strip()[:200],
            "description": str(desc_cell).strip()[:500],
        })
    
    return contacts


def import_to_db(contacts):
    """Import contacts into SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            name TEXT,
            description TEXT,
            group_name TEXT DEFAULT 'default',
            status TEXT DEFAULT 'active',
            last_contacted TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    added = 0
    skipped = 0
    for c in contacts:
        # Check if already exists
        existing = cur.execute(
            "SELECT id FROM contacts WHERE username = ?", (c["username"],)
        ).fetchone()
        
        if existing:
            skipped += 1
            continue
        
        cur.execute(
            "INSERT INTO contacts (username, name, description, group_name) VALUES (?, ?, ?, ?)",
            (c["username"], c["name"], c["description"], "hr_recruiters")
        )
        added += 1
    
    conn.commit()
    conn.close()
    return added, skipped


def main():
    print("📥 Загрузка контактов из Google Sheets...")
    contacts = fetch_sheet()
    print(f"📊 Найдено {len(contacts)} контактов в таблице")
    
    print("💾 Импорт в базу данных...")
    added, skipped = import_to_db(contacts)
    
    print(f"✅ Импорт завершён!")
    print(f"   Добавлено: {added}")
    print(f"   Пропущено (уже есть): {skipped}")
    print(f"   Всего в таблице: {len(contacts)}")


if __name__ == "__main__":
    main()
