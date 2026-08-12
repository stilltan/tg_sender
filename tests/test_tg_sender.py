"""Внутренние тесты TG Sender — прогон на КОПИИ БД, ничего боевого не трогается.

Запуск (на сервере):
  cd /tmp/tg_sender_tests && /opt/tg_sender/venv/bin/python -m unittest test_tg_sender -v
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # папка с web/
sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(SRC, "web"))

# --- тестовая БД: свежая копия схемы (создаём из воздуха, данные не нужны для схемы) ---
_TMP = tempfile.mkdtemp(prefix="tgsender_test_")
TEST_DB = os.path.join(_TMP, "test.db")

# Старая схема (как в боевой БД до миграции): message_log БЕЗ account_id,
# campaigns БЕЗ template_id/messages_per_account
OLD_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE tg_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, phone TEXT NOT NULL, api_id INTEGER, api_hash TEXT,
    session_string TEXT, status TEXT DEFAULT 'inactive', last_used TEXT,
    messages_sent INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL, name TEXT, description TEXT, group_name TEXT DEFAULT 'default',
    status TEXT DEFAULT 'active', last_contacted TEXT, notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE message_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, text TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, message_text TEXT, contact_group TEXT DEFAULT 'all',
    status TEXT DEFAULT 'draft', delay_min INTEGER DEFAULT 30, delay_max INTEGER DEFAULT 60,
    total_contacts INTEGER DEFAULT 0, sent_count INTEGER DEFAULT 0, failed_count INTEGER DEFAULT 0,
    started_at TEXT, completed_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE message_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER, contact_id INTEGER, contact_username TEXT,
    status TEXT NOT NULL, error_message TEXT, sent_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def make_old_db(path):
    c = sqlite3.connect(path)
    c.executescript(OLD_SCHEMA)
    # немного данных, чтобы проверить, что миграция их не теряет
    c.execute("INSERT INTO contacts (username, name, group_name, status) VALUES ('@test1', 'Тест', 'default', 'active')")
    c.execute("INSERT INTO contacts (username, name, group_name, status) VALUES ('@test2', 'Тест2', 'default', 'active')")
    c.execute("INSERT INTO tg_accounts (phone, status) VALUES ('+70000000001', 'active')")
    c.execute("INSERT INTO message_templates (name, text) VALUES ('Привет', 'Здравствуйте, {name}!')")
    c.commit()
    c.close()


class TestMigration(unittest.TestCase):
    """Миграция старой схемы → новой, без потери данных."""

    def setUp(self):
        self.db = TEST_DB
        if os.path.exists(self.db):
            os.remove(self.db)
        make_old_db(self.db)
        # подменяем путь БД в модулях под тестовую копию
        import web.app as app
        import web.sender_engine as eng
        app.DB_PATH = self.db
        eng.DB_PATH = self.db

    def test_migrate_adds_columns(self):
        import web.app as app
        app.migrate_db()
        c = sqlite3.connect(self.db)
        log_cols = {r[1] for r in c.execute("PRAGMA table_info(message_log)")}
        camp_cols = {r[1] for r in c.execute("PRAGMA table_info(campaigns)")}
        c.close()
        self.assertIn("account_id", log_cols, "message_log.account_id не добавлен")
        self.assertIn("template_id", camp_cols, "campaigns.template_id не добавлен")
        self.assertIn("messages_per_account", camp_cols, "campaigns.messages_per_account не добавлен")

    def test_migrate_keeps_data(self):
        import web.app as app
        app.migrate_db()
        c = sqlite3.connect(self.db)
        n = c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        accounts = c.execute("SELECT COUNT(*) FROM tg_accounts").fetchone()[0]
        c.close()
        self.assertEqual(n, 2, "данные контактов потеряны")
        self.assertEqual(accounts, 1, "данные аккаунтов потеряны")

    def test_migrate_idempotent(self):
        import web.app as app
        app.migrate_db()
        app.migrate_db()  # повторный прогон не должен падать
        c = sqlite3.connect(self.db)
        log_cols = {r[1] for r in c.execute("PRAGMA table_info(message_log)")}
        c.close()
        self.assertIn("account_id", log_cols)

    def test_log_message_writes_account_id(self):
        import web.app as app
        app.migrate_db()
        import web.sender_engine as eng
        eng.DB_PATH = self.db
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO campaigns (name, contact_group, status) VALUES ('Кампания', 'all', 'draft')")
        c.commit()
        c.close()
        eng.log_message(1, 7, "@test1", "sent")
        c = sqlite3.connect(self.db)
        row = c.execute("SELECT account_id, contact_username, status FROM message_log").fetchone()
        c.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 7, "account_id не сохранился")
        self.assertEqual(row[1], "@test1")
        self.assertEqual(row[2], "sent")

    def test_stats_query_works_after_migration(self):
        """Тот запрос, что падал на боевой БД ('no such column: ml.account_id')."""
        import web.app as app
        app.migrate_db()
        c = sqlite3.connect(self.db)
        # точный запрос из /accounts
        c.execute("INSERT INTO tg_accounts (phone, status) VALUES ('+70000000002', 'active')")
        c.execute("INSERT INTO tg_accounts (phone, status) VALUES ('+70000000003', 'active')")
        c.commit()
        rows = c.execute(
            "SELECT a.id, a.phone, a.status, "
            "(SELECT COUNT(*) FROM message_log ml WHERE ml.account_id = a.id AND ml.status = 'sent') as sent, "
            "(SELECT COUNT(*) FROM message_log ml WHERE ml.account_id = a.id AND ml.status = 'failed') as failed "
            "FROM tg_accounts a"
        ).fetchall()
        c.close()
        self.assertEqual(len(rows), 3)


class TestAuth(unittest.TestCase):
    def test_hash_verify_roundtrip(self):
        import web.app as app
        h = app.hash_password("secret-pass-123")
        self.assertTrue(app.verify_password("secret-pass-123", h))
        self.assertFalse(app.verify_password("wrong", h))

    def test_init_db_creates_admin_and_tables(self):
        import web.app as app
        db2 = os.path.join(_TMP, "fresh.db")
        if os.path.exists(db2):
            os.remove(db2)
        app.DB_PATH = db2
        app.init_db()
        c = sqlite3.connect(db2)
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        admin = c.execute("SELECT username FROM users WHERE username='admin'").fetchone()
        c.close()
        for t in ("users", "tg_accounts", "contacts", "message_templates", "campaigns", "message_log"):
            self.assertIn(t, tables, f"нет таблицы {t}")
        self.assertIsNotNone(admin, "admin не создан")
        # новая схема сразу с нужными колонками
        c = sqlite3.connect(db2)
        log_cols = {r[1] for r in c.execute("PRAGMA table_info(message_log)")}
        c.close()
        self.assertIn("account_id", log_cols)


class TestSecurity(unittest.TestCase):
    """Защита как в I•Match: журнал действий, лимит входов, IP-фильтр, ключ сессии."""

    def setUp(self):
        self.db = os.path.join(_TMP, "sec_test.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        import web.app as app
        app.DB_PATH = self.db
        app.init_db()

    def test_log_action_writes_and_list(self):
        import web.app as app
        app.log_action("admin", "login", "успешный вход", "127.0.0.1")
        app.log_action("admin", "campaign_start", "кампания #1", "10.0.0.1")
        items = app.admin_log_list()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["action"], "campaign_start")
        self.assertEqual(items[0]["ip"], "10.0.0.1")
        self.assertEqual(items[1]["username"], "admin")

    def test_login_rate_limit(self):
        import web.app as app
        ip = "192.168.0.55"
        app._login_attempts.clear()
        app.login_rate_reset(ip)
        for _ in range(app.LOGIN_MAX_ATTEMPTS):
            app.login_rate_check(ip)      # до лимита — ок
            app.login_rate_fail(ip)
        with self.assertRaises(Exception):
            app.login_rate_check(ip)      # превышен лимит → HTTPException(429)
        app.login_rate_reset(ip)
        app.login_rate_check(ip)          # после сброса снова ок

    def test_ip_allowed(self):
        import web.app as app
        app.IP_ALLOWLIST = {"10.1.1.1"}
        class FakeRequest:
            client = type("C", (), {"host": "127.0.0.1"})()
            headers = {}
        # localhost разрешён всегда
        self.assertTrue(app.ip_allowed(FakeRequest()))
        class FakeRequest2:
            client = type("C", (), {"host": "8.8.8.8"})()
            headers = {}
        self.assertFalse(app.ip_allowed(FakeRequest2()))
        class FakeRequest3:
            client = type("C", (), {"host": "10.1.1.1"})()
            headers = {}
        self.assertTrue(app.ip_allowed(FakeRequest3()))
        app.IP_ALLOWLIST = set()

    def test_client_ip_xff(self):
        import web.app as app
        class FakeRequest:
            client = type("C", (), {"host": "127.0.0.1"})()
            headers = {"x-forwarded-for": "203.0.113.9, 10.0.0.1"}
        self.assertEqual(app.client_ip(FakeRequest()), "203.0.113.9")

    def test_init_db_creates_admin_log_table(self):
        import web.app as app
        c = sqlite3.connect(self.db)
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        c.close()
        self.assertIn("admin_log", tables)


class TestContactsEngine(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(_TMP, "contacts_test.db")
        if os.path.exists(self.db):
            os.remove(self.db)
        make_old_db(self.db)
        import web.app as app
        import web.sender_engine as eng
        app.DB_PATH = self.db
        eng.DB_PATH = self.db
        app.migrate_db()

    def test_get_contacts_for_campaign(self):
        import web.app as app
        import web.sender_engine as eng
        c = sqlite3.connect(app.DB_PATH)
        c.execute("INSERT INTO campaigns (name, contact_group, status) VALUES ('Кампания', 'default', 'draft')")
        c.commit()
        camp_id = c.execute("SELECT id FROM campaigns LIMIT 1").fetchone()[0]
        c.close()
        contacts, campaign = eng.get_contacts_for_campaign(camp_id)
        self.assertEqual(len(contacts), 2)
        self.assertEqual(campaign["name"], "Кампания")
        # контакты уже отмеченные 'sent' исключаются
        eng.log_message(camp_id, 1, "@test1", "sent")
        contacts2, _ = eng.get_contacts_for_campaign(camp_id)
        self.assertEqual(len(contacts2), 1)


if __name__ == "__main__":
    unittest.main()
