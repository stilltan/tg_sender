import csv
import sqlite3

CSV_PATH = '/opt/tg_sender/uploads/contacts.csv'
DB_PATH = '/opt/tg_sender/data/sender.db'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Get usernames with dates (already contacted)
to_remove = []
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        date = (row.get('Дата рассылки в ШМ') or '').strip()
        url = (row.get('SSYLKA') or '').strip()
        if date and url:
            username = url.replace('t.me/', '').replace('@', '').strip()
            if username:
                to_remove.append(username)

print(f"Contacts with date (to remove): {len(to_remove)}")

# Remove them
removed = 0
for username in to_remove:
    cur.execute("DELETE FROM contacts WHERE username = ?", (username,))
    removed += cur.rowcount

conn.commit()

# Verify
total = cur.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
active = cur.execute("SELECT COUNT(*) FROM contacts WHERE status='active'").fetchone()[0]
conn.close()

print(f"Removed: {removed}")
print(f"Remaining: {total} (active: {active})")
