"""
SQLite database for Telegram Sender Bot.
Tables: contacts, messages, campaigns, admins
"""
from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_super BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message_text TEXT NOT NULL,
            contact_group TEXT DEFAULT 'all',
            status TEXT DEFAULT 'draft',
            delay_min INTEGER DEFAULT 30,
            delay_max INTEGER DEFAULT 60,
            total_contacts INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            contact_id INTEGER,
            contact_username TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
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
    
    conn.commit()
    conn.close()


# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def is_admin(telegram_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    conn.close()
    return row is not None


def get_all_admins() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM admins").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_admin(telegram_id: int, username: str = None, first_name: str = None, is_super: bool = False) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO admins (telegram_id, username, first_name, is_super) 
           VALUES (?, ?, ?, ?)""",
        (telegram_id, username, first_name, is_super)
    )
    conn.commit()
    conn.close()


def remove_admin(telegram_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()


# ============================================================
# CONTACT FUNCTIONS
# ============================================================

def add_contact(username: str, name: str = None, description: str = None, group_name: str = "default") -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO contacts (username, name, description, group_name) 
           VALUES (?, ?, ?, ?)""",
        (username, name, description, group_name)
    )
    conn.commit()
    contact_id = cur.lastrowid
    conn.close()
    return contact_id


def get_contact(contact_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_contacts(status: str = None, group_name: str = None) -> List[Dict]:
    conn = get_conn()
    query = "SELECT * FROM contacts WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if group_name and group_name != "all":
        query += " AND group_name = ?"
        params.append(group_name)
    
    query += " ORDER BY created_at DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_contact_groups() -> List[str]:
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT group_name FROM contacts ORDER BY group_name").fetchall()
    conn.close()
    return [r['group_name'] for r in rows]


def update_contact(contact_id: int, **kwargs) -> None:
    conn = get_conn()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [contact_id]
    conn.execute(f"UPDATE contacts SET {set_clause}, updated_at = ? WHERE id = ?", 
                 list(kwargs.values()) + [now_str(), contact_id])
    conn.commit()
    conn.close()


def mark_contact(contact_id: int, status: str = "contacted") -> None:
    """Mark contact as contacted/not interested/etc."""
    conn = get_conn()
    conn.execute(
        "UPDATE contacts SET status = ?, last_contacted = ?, updated_at = ? WHERE id = ?",
        (status, now_str(), now_str(), contact_id)
    )
    conn.commit()
    conn.close()


def delete_contact(contact_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()


def delete_all_contacts() -> None:
    conn = get_conn()
    conn.execute("DELETE FROM contacts")
    conn.commit()
    conn.close()


def import_contacts_from_list(contacts: List[Dict], group_name: str = "imported") -> int:
    """Import contacts from list of dicts with keys: username, name, description"""
    conn = get_conn()
    count = 0
    for c in contacts:
        username = c.get('username', '').strip()
        if not username:
            continue
        # Remove @ if present
        if username.startswith('@'):
            username = username[1:]
        # Remove t.me/ prefix if present
        if 't.me/' in username:
            username = username.split('t.me/')[-1]
        
        conn.execute(
            """INSERT INTO contacts (username, name, description, group_name) 
               VALUES (?, ?, ?, ?)""",
            (username, c.get('name'), c.get('description'), group_name)
        )
        count += 1
    
    conn.commit()
    conn.close()
    return count


# ============================================================
# TEMPLATE FUNCTIONS
# ============================================================

def add_template(name: str, text: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO message_templates (name, text) VALUES (?, ?)",
        (name, text)
    )
    conn.commit()
    template_id = cur.lastrowid
    conn.close()
    return template_id


def get_all_templates() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM message_templates ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_template(template_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM message_templates WHERE id = ?", (template_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_template(template_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


# ============================================================
# CAMPAIGN FUNCTIONS
# ============================================================

def create_campaign(name: str, message_text: str, contact_group: str = "all",
                    delay_min: int = 30, delay_max: int = 60) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO campaigns (name, message_text, contact_group, delay_min, delay_max) 
           VALUES (?, ?, ?, ?, ?)""",
        (name, message_text, contact_group, delay_min, delay_max)
    )
    conn.commit()
    campaign_id = cur.lastrowid
    conn.close()
    return campaign_id


def get_campaign(campaign_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_campaigns() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_campaign(campaign_id: int, **kwargs) -> None:
    conn = get_conn()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [campaign_id]
    conn.execute(f"UPDATE campaigns SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_campaign(campaign_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM message_log WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()


# ============================================================
# MESSAGE LOG FUNCTIONS
# ============================================================

def log_message(campaign_id: int, contact_id: int, contact_username: str, 
                status: str, error_message: str = None) -> None:
    conn = get_conn()
    conn.execute(
        """INSERT INTO message_log (campaign_id, contact_id, contact_username, status, error_message) 
           VALUES (?, ?, ?, ?, ?)""",
        (campaign_id, contact_id, contact_username, status, error_message)
    )
    conn.commit()
    conn.close()


def get_campaign_logs(campaign_id: int) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM message_log WHERE campaign_id = ? ORDER BY sent_at DESC",
        (campaign_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# STATISTICS
# ============================================================

def get_statistics() -> Dict[str, Any]:
    conn = get_conn()
    
    total_contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    active_contacts = conn.execute("SELECT COUNT(*) FROM contacts WHERE status = 'active'").fetchone()[0]
    contacted = conn.execute("SELECT COUNT(*) FROM contacts WHERE status = 'contacted'").fetchone()[0]
    not_interested = conn.execute("SELECT COUNT(*) FROM contacts WHERE status = 'not_interested'").fetchone()[0]
    blocked = conn.execute("SELECT COUNT(*) FROM contacts WHERE status = 'blocked'").fetchone()[0]
    
    total_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
    completed_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'completed'").fetchone()[0]
    
    total_sent = conn.execute("SELECT SUM(sent_count) FROM campaigns").fetchone()[0] or 0
    total_failed = conn.execute("SELECT SUM(failed_count) FROM campaigns").fetchone()[0] or 0
    
    conn.close()
    
    return {
        'total_contacts': total_contacts,
        'active_contacts': active_contacts,
        'contacted': contacted,
        'not_interested': not_interested,
        'blocked': blocked,
        'total_campaigns': total_campaigns,
        'completed_campaigns': completed_campaigns,
        'total_sent': total_sent,
        'total_failed': total_failed,
        'success_rate': round(total_sent / (total_sent + total_failed) * 100, 1) if (total_sent + total_failed) > 0 else 0
    }


def get_contacts_by_status() -> Dict[str, int]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM contacts GROUP BY status"
    ).fetchall()
    conn.close()
    return {row['status']: row['cnt'] for row in rows}
