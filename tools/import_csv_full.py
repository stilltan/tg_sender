import csv
import sqlite3

CSV_PATH = '/opt/tg_sender/uploads/contacts.csv'
DB_PATH = '/opt/tg_sender/data/sender.db'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Clear existing contacts
cur.execute('DELETE FROM contacts')

added = 0
skipped = 0

with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        url = (row.get('SSYLKA') or '').strip()
        name = (row.get('NAME') or '').strip()
        desc = (row.get('OPISANIYE') or '').strip()
        
        if not url:
            continue
        
        # Clean username
        username = url.replace('t.me/', '').replace('@', '').strip()
        if not username:
            continue
        
        # Check if already exists
        existing = cur.execute('SELECT id FROM contacts WHERE username = ?', (username,)).fetchone()
        if existing:
            skipped += 1
            continue
        
        cur.execute(
            'INSERT INTO contacts (username, name, description, group_name, status) VALUES (?, ?, ?, ?, ?)',
            (username, name[:200], desc[:500], 'recruiters', 'active')
        )
        added += 1

conn.commit()

# Verify
total = cur.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]
active = cur.execute("SELECT COUNT(*) FROM contacts WHERE status='active'").fetchone()[0]
conn.close()

print(f'Added: {added}, Skipped: {skipped}, Total: {total}, Active: {active}')
