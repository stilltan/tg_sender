import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sender.db')

def import_contacts(filepath, group='hr_recruiters'):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Ensure table exists
    cur.execute('''CREATE TABLE IF NOT EXISTS contacts (
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
    )''')
    
    added = 0
    skipped = 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 1:
                continue
            
            username = parts[0].strip().lstrip('@')
            if 't.me/' in username:
                username = username.split('t.me/')[-1]
            
            name = parts[1] if len(parts) > 1 else ''
            desc = parts[2] if len(parts) > 2 else ''
            
            if not username:
                continue
            
            # Check duplicate
            existing = cur.execute('SELECT id FROM contacts WHERE username = ?', (username,)).fetchone()
            if existing:
                skipped += 1
                continue
            
            cur.execute(
                'INSERT INTO contacts (username, name, description, group_name) VALUES (?, ?, ?, ?)',
                (username, name[:200], desc[:500], group)
            )
            added += 1
    
    conn.commit()
    conn.close()
    return added, skipped

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'contacts_base.txt'
    group = sys.argv[2] if len(sys.argv) > 2 else 'hr_recruiters'
    
    print(f'📥 Импорт из {filepath}...')
    added, skipped = import_contacts(filepath, group)
    print(f'✅ Добавлено: {added}, пропущено: {skipped}')
