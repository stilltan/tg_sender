# AGENT HANDOFF — TG Sender Project
> Created: 2026-08-13
> Status: Fully operational

---

## 1. КТО ТЫ

Ты агент, который продолжает работу над проектом **TG Sender** — система рассылки сообщений в Telegram через реальные аккаунты (не боты). Проект развёрнут на VPS, код на GitHub, веб-интерфейс работает.

Пользователь: **@Cursdworld** (Telegram ID: 7627878199) — HR рекрутер, автоматизирует рассылку рекрутерам.

---

## 2. РЕПОЗИТОРИЙ

```
GitHub: https://github.com/stilltan/tg_sender
Owner: stilltan
```

**Клонирование (с токеном):**
```
git clone https://[GITHUB_TOKEN - get from server: /opt/tg_sender/.env or ask user]@github.com/stilltan/tg_sender.git
```

**Push:**
```bash
cd tg_sender
git remote set-url origin https://[GITHUB_TOKEN - get from server: /opt/tg_sender/.env or ask user]@github.com/stilltan/tg_sender.git
git add -A && git commit -m "msg" && git push origin main
```

> ⚠️ Токен `[GITHUB_TOKEN - get from server: /opt/tg_sender/.env or ask user]` — GitHub PAT. Если истёк, создай новый в Settings → Developer settings → Personal access tokens.

---

## 3. СЕРВЕР

### SSH доступ
```
IP: 158.160.6.22
User: agent2
```

**SSH ключ (agent2):**
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBYg9jlIb02ts4ZgguFrRS5AqcsicTW5d/5D9iJ9352aQAAAKC5A6YWuQOm
FgAAAAtzc2gtZWQyNTUxOQAAACBYg9jlIb02ts4ZgguFrRS5AqcsicTW5d/5D9iJ9352aQ
AAAECHwDPfBCDUab2LT8p3GF+OFCvCldBqUZWb7yao7T92gFiD2OUhvTa2zhmCC4WtFLkC
pyyJxNbl3/kP2In3fnZpAAAAHHRlbXAtYWdlbnQyLXVudGlsLTIwMjYtMDgtMTkB
-----END OPENSSH PRIVATE KEY-----
```

Сохрани в `~/.ssh/agent2_key`, выполни:
```bash
chmod 600 ~/.ssh/agent2_key
ssh -i ~/.ssh/agent2_key agent2@158.160.6.22
```

**Срок действия:** до 19 августа 2026

### Веб-интерфейс
```
URL: http://158.160.6.22:8000
Логин: admin
Пароль: rs7vSQhh00Sfsbid
```

### Telegram Bot
```
Username: @FAWWWWWWWWWWWWW_bot
Token: [BOT_TOKEN - get from server: /opt/tg_sender/.env]
Admin ID: 7627878199 (@Cursdworld)
```

---

## 4. СОСТОЯНИЕ СЕРВЕРА

### Сервисы
| Сервис | Порт | Статус | Примечание |
|--------|------|--------|------------|
| imatch-ankety | - | ✅ | НЕ ТРОГАТЬ (чужой) |
| imatch-school | - | ✅ | НЕ ТРОГАТЬ (чужой) |
| imatch-vitrina | - | ✅ | НЕ ТРОГАТЬ (чужой) |
| imatch-web | 8080 | ✅ | НЕ ТРОГАТЬ (чужой) |
| **tg-sender-web** | **8000** | ✅ | **Наш веб-дашборд** |
| rustdesk-hbbs | 21115 | ✅ | RustDesk (не используется) |
| rustdesk-hbbr | 21117 | ✅ | RustDesk (не используется) |

**НЕ ТРОГАЙ** сервисы imatch-* и файлы в `/opt/imatch/`. Это чужой проект.

### Порты (ufw)
```
22, 80, 443 - стандартные
8000        - tg-sender-web
8080        - imatch-web (localhost only)
8088        - tg-monitor (запускается вручную)
21115-21119 - RustDesk (не используется)
```

---

## 5. ПРОЕКТ — СТРУКТУРА

### На сервере (`/opt/tg_sender/`)
```
web/
├── app.py                  # FastAPI — основные руты, авторизация, кампании
├── tg_client.py            # Telethon — Telegram клиент (просмотр чатов, отправка)
├── tg_client_routes.py     # FastAPI руты для Telegram клиента (/tg, /api/tg/*)
├── sender_engine.py        # Движок рассылки (spintax, delays, flood rotation)
├── antispam.py             # Анти-спам (лимиты, прогрев, delays)
├── spintax_engine.py       # Spintax движок ({вар1|вар2|вар3})
├── tg_monitor_web.py       # Мониторинг чатов (отдельный HTTP на 8088)
├── templates/              # Jinja2 HTML шаблоны
│   ├── base.html          # Базовый layout (sidebar, навигация)
│   ├── login.html         # Страница входа
│   ├── dashboard.html     # Дашборд
│   ├── accounts.html      # Управление аккаунтами
│   ├── contacts.html      # Контакты
│   ├── templates.html     # Шаблоны сообщений
│   ├── campaigns.html     # Список рассылок
│   ├── new_campaign.html  # Создание рассылки
│   ├── analytics.html     # Аналитика
│   ├── settings.html      # Настройки + управление пользователями
│   ├── monitor.html       # Мониторинг чатов (из tg_monitor_web.py)
│   └── tg_client.html     # Telegram Web клиент
├── static/styles.css       # CSS (Linear+Raycast dark theme)
│
core/
├── config.py              # Загрузка .env, константы
├── db.py                  # SQLite операции (контакты, кампании, логи)
│
data/
└── sender.db              # SQLite база данных

sessions/                   # Telethon .session файлы
accounts/                   # TDATA папки + JSON + 2FA
proxy.conf                  # MTProto прокси (host:port:secret)
.env                        # Токены и настройки
```

### В репозитории (GitHub)
```
web/                        # Весь веб-код
core/                       # Ядро
tools/                      # Скрипты (импорт, тесты, баны)
docs/                       # Документация
tests/                      # Тесты (unittest)
AGENT_HANDOFF.md            # Этот файл
AGENT_CHECKLIST.md          # Чеклист
SECURITY_NOTES.md           # Безопасность
requirements.txt            # Зависимости
```

### Технологии
- Python 3.12
- FastAPI + uvicorn (веб)
- Telethon 1.44.0 (Telegram MTProto)
- SQLite (БД)
- Jinja2 (шаблоны)
- systemd (сервисы)

---

## 6. TELEGRAM АККАУНТЫ

| Телефон | Username | Имя | Статус | 2FA |
|---------|----------|-----|--------|-----|
| +919084101190 | @i_match_Oks | I_Match_Oksana | ✅ active | None |
| +919085691621 | @i_match_Oksana | I_Match_OKSANA | ✅ active | None |
| +919087271255 | @i_match_0ksana | I_Match_Oksana gart | ✅ active | None |
| +919087424900 | - | Niraj K | ❌ inactive | None |

**API (общий для всех):**
```
API ID: 2040
API Hash: b18441a1ff607e10a989891a5462e627
```

**Session файлы:** `/opt/tg_sender/sessions/919*.session`  
**TDATA:** `/opt/tg_sender/accounts/919*/tdata/`  
**2FA:** `/opt/tg_sender/accounts/919*/twoFA.txt` (все None)

---

## 7. ПРОКСИ

### MTProto (для Telethon — пользовательские аккаунты)
```
Файл: /opt/tg_sender/proxy.conf
Host: 94.130.191.53
Port: 8443
Secret: dd104462821249bd7ac519130220c25d09
```

### Cloudflare Worker (для Bot API)
```
URL: https://imatch-tgproxy.stilltanvoid.workers.dev/bot
Файл: /opt/tg_sender/.env → BOT_API_BASE_URL
```

---

## 8. БАЗА ДАННЫХ

### SQLite: `/opt/tg_sender/data/sender.db`

| Таблица | Назначение | Записей |
|---------|------------|--------|
| `users` | Пользователи веба | 1 (admin) |
| `tg_accounts` | Telegram аккаунты | 4 |
| `contacts` | Контакты для рассылки | 51 |
| `message_templates` | Шаблоны сообщений | 1 |
| `campaigns` | Рассылки | 0 |
| `message_log` | Лог отправок | ~5 |

---

## 9. ВЕБ-ИНТЕРФЕЙС — СТРАНИЦЫ

| Путь | Описание |
|------|----------|
| `/login` | Вход |
| `/dashboard` | Дашборд со статистикой |
| `/accounts` | Telegram аккаунты (добавить, удалить, снять блоки) |
| `/contacts` | Контакты (импорт, статусы, фильтры) |
| `/templates` | Шаблоны сообщений (spintax) |
| `/campaigns` | Список рассылок |
| `/campaigns/new` | Создание рассылки |
| `/analytics` | Аналитика (графики) |
| `/settings` | Настройки + пользователи + экспорт |
| `/logs` | Журнал действий |
| `/tg` | **Telegram Web клиент** |

### API (для Telegram клиента)
| Путь | Метод | Описание |
|------|-------|----------|
| `/api/tg/{phone}/dialogs` | GET | Список чатов |
| `/api/tg/{phone}/messages/{id}` | GET | Сообщения чата |
| `/api/tg/{phone}/send/{id}` | POST | Отправить сообщение |
| `/api/tg/{phone}/read/{id}` | POST | Отметить прочитанным |
| `/export/contacts` | GET | Экспорт CSV |

---

## 10. ТЕСТЫ

### Файлы тестов
```
tests/test_tg_sender.py    # 13 unittest тестов (схема БД, миграция, контакты)
tools/test_monitor.py      # Тест мониторинга чатов
tools/test_all_accounts.py # Тест всех аккаунтов (отправка)
tools/test_proxy.py        # Тест MTProto прокси
tools/fast_test_proxy.py   # Быстрый тест прокси (параллельно)
tools/check_ban_status.py  # Проверка банов через @SpamBot
```

### Запуск тестов
```bash
cd /opt/tg_sender
source venv/bin/activate

# Unit тесты (на копии БД, ничего боевого не трогает)
cd /tmp && cp -r /opt/tg_sender/tests .
python -m unittest tests.test_tg_sender -v

# Тест аккаунтов
python tools/test_all_accounts.py

# Проверка банов
python tools/check_ban_status.py

# Тест прокси
python tools/fast_test_proxy.py
```

### Что тестируется
- Схема БД (старая → новая миграция)
- Добавление контактов
- Создание кампаний
- Авторизация аккаунтов через прокси
- Отправка тестовых сообщений
- Проверка статуса @SpamBot

---

## 11. КОМАНДЫ УПРАВЛЕНИЯ

```bash
# === Подключение ===
ssh -i ~/.ssh/agent2_key agent2@158.160.6.22

# === Сервисы ===
sudo systemctl status tg-sender-web      # Статус дашборда
sudo systemctl restart tg-sender-web     # Рестарт дашборда
sudo journalctl -u tg-sender-web -f      # Логи дашборда

# === Мониторинг (запуск вручную) ===
cd /opt/tg_sender
pkill -f tg_monitor_web
nohup venv/bin/python web/tg_monitor_web.py &

# === База данных ===
cd /opt/tg_sender && source venv/bin/activate
python3 -c "from core import db; db.init_db(); print(db.get_statistics())"
python3 -c "from core import db; db.init_db(); print(len(db.get_all_contacts()))"

# === Git ===
cd /home/user/tg_sender
git remote set-url origin https://[GITHUB_TOKEN - get from server: /opt/tg_sender/.env or ask user]@github.com/stilltan/tg_sender.git
git add -A && git commit -m "msg" && git push origin main

# === Анти-бан ===
python tools/check_ban_status.py     # Проверить баны
python tools/unban_accounts.py       # Снять баны через @SpamBot
```

---

## 12. АНТИ-СПАМ СИСТЕМА

Реализована в `web/sender_engine.py` + `web/antispam.py`:

| Компонент | Файл | Описание |
|-----------|------|----------|
| Spintax | `spintax_engine.py` | `{Привет\|Здравствуй\|Хай}` → уникальные тексты |
| Умные задержки | `antispam.py` | 2-10 мин по возрасту аккаунта |
| Дневные лимиты | `antispam.py` | 3-80 сообщений/день |
| Проверка первого ЛС | `sender_engine.py` | Запрет ссылок |
| Окно отправки | `sender_engine.py` | 9:00-22:00 |
| Ротация аккаунтов | `sender_engine.py` | При flood → следующий аккаунт |
| Авто-бан | `tools/unban_accounts.py` | @SpamBot апелляция |

**Документация:** `docs/TELEGRAM_SPAM_BYPASS.md`

---

## 13. ИЗВЕСТНЫЕ ПРОБЛЕМЫ

1. **RustDesk** — установлен, но не подключается к hbbs. Не критично.
2. **4-й аккаунт** (+919087424900) — не авторизован.
3. **Telegram API заблокирован** — всё через MTProto прокси.
4. **Мониторинг (8088)** — запускается вручную, не systemd сервис.
5. **Бот tg-sender** — удалён (сервис tg-sender.service отключён).

---

## 14. ЧТО ДОДЕЛАТЬ

1. Добавить больше контактов (сейчас 51)
2. Создать несколько шаблонов с spintax
3. Протестировать рассылку на малой группе
4. Добавить SSL (HTTPS) через Caddy/nginx
5. Сделать мониторинг сервисом systemd
6. Авторизовать 4-й аккаунт
7. Улучшить дизайн tg_client.html
8. Добавить уведомления при ответах на сообщения
