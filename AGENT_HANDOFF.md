# AGENT HANDOFF — TG Sender Project
> Created: 2026-08-13
> Status: Fully operational

---

## 1. КТО ТЫ

Ты агент, который продолжает работу над проектом **TG Sender** — система рассылки сообщений в Telegram через реальные аккаунты (не боты). Проект развёрнут на VPS, код на GitHub, веб-интерфейс работает.

---

## 2. ДОСТУПЫ

### Сервер (Yandex Cloud VPS)
```
IP: 158.160.6.22
OS: Ubuntu 24.04 (Noble)
SSH user: agent2
SSH key: файл agent2_key (ключи лежат отдельно, не в репо)
```

**Подключение:**
```bash
ssh -i ~/.ssh/agent2_key agent2@158.160.6.22
```

### GitHub
```
Repo: https://github.com/stilltan/tg_sender
Owner: stilltan
```

### Веб-интерфейс
```
URL: http://158.160.6.22:8000
Логин: admin
Пароль: (см. /opt/tg_sender/.admin_credentials на сервере)
```

### Telegram Bot
```
Username: @FAWWWWWWWWWWWWW_bot
Admin ID: 7627878199 (@Cursdworld)
```

---

## 3. СОСТОЯНИЕ СЕРВЕРА

### Сервисы (все работают)
| Сервис | Порт | Назначение |
|--------|------|------------|
| imatch-ankety | - | I-Match бот анкет (НЕ ТРОГАТЬ) |
| imatch-school | - | I-Match школа (НЕ ТРОГАТЬ) |
| imatch-vitrina | - | I-Match витрина (НЕ ТРОГАТЬ) |
| imatch-web | 8080 (localhost) | I-Match сайт (НЕ ТРОГАТЬ) |
| **tg-sender-web** | **8000** | **Наш веб-дашборд** |
| rustdesk | - | RustDesk (не используется) |
| rustdesk-hbbs | 21115-21116 | RustDesk signaling (не используется) |
| rustdesk-hbbr | 21117 | RustDesk relay (не используется) |

**ВАЖНО:** Сервисы imatch-* чужие. Не трогай их. Не меняй порты. Не удаляй файлы в /opt/imatch/.

### Порты (открыты в ufw)
```
22    - SSH
8000  - tg-sender-web (наш)
8080  - imatch-web (чужой, localhost only)
8088  - tg-monitor (наш, запускается вручную)
21115-21119 - RustDesk (не используется)
```

---

## 4. ПРОЕКТ

### Структура на сервере
```
/opt/tg_sender/
├── web/                    # Веб-приложение (FastAPI)
│   ├── app.py             # Основные руты
│   ├── tg_client.py       # Telegram клиент (Telethon)
│   ├── tg_client_routes.py# API для Telegram клиента
│   ├── sender_engine.py   # Движок рассылки
│   ├── antispam.py        # Защита от спама
│   ├── spintax_engine.py  # Уникализация текстов
│   ├── tg_monitor_web.py  # Мониторинг чатов (порт 8088)
│   ├── templates/          # HTML шаблоны (Jinja2)
│   └── static/styles.css  # CSS стили (Linear+Raycast dark)
├── core/                   # Конфигурация и БД
│   ├── config.py          # Настройки из .env
│   └── db.py              # SQLite операции
├── data/                   # База данных SQLite
│   └── sender.db          # Основная БД
├── sessions/               # Telegram сессии (.session файлы)
├── accounts/               # TDATA папки аккаунтов
├── .env                    # Переменные окружения
├── proxy.conf              # MTProto прокси
├── .admin_credentials      # Логин/пароль веб-админки
└── tools/                  # Скрипты
```

### Структура репозитория (GitHub)
```
tg_sender/
├── web/                    # Веб-приложение
├── core/                   # Ядро
├── tools/                  # Скрипты инструментов
├── docs/                   # Документация
│   └── TELEGRAM_SPAM_BYPASS.md  # Полный разбор анти-спама
├── AGENT_HANDOFF.md        # Этот файл
├── AGENT_CHECKLIST.md      # Чеклист для агента
├── SECURITY_NOTES.md       # Заметки по безопасности
├── requirements.txt        # Python зависимости
└── .env.example            # Пример .env
```

### Технологии
- **Backend:** Python 3.12 + FastAPI
- **Telegram:** Telethon 1.44.0 (MTProto)
- **БД:** SQLite
- **Прокси:** MTProto (для Telethon) + Cloudflare Worker (для Bot API)
- **Деплой:** systemd сервисы
- **Дизайн:** Dark theme в стиле Linear.app + Raycast (CSS в static/styles.css)

---

## 5. TELEGRAM АККАУНТЫ

### Данные аккаунтов
| Телефон | Username | Имя | Статус |
|---------|----------|-----|--------|
| +919084101190 | @i_match_Oks | I_Match_Oksana | ✅ active |
| +919085691621 | @i_match_Oksana | I_Match_OKSANA | ✅ active |
| +919087271255 | @i_match_0ksana | I_Match_Oksana gart | ✅ active |
| +919087424900 | - | Niraj K | ❌ inactive |

### API для всех аккаунтов
```
API ID: 2040
API Hash: b18441a1ff607e10a989891a5462e627
```

### Session файлы: `/opt/tg_sender/sessions/`
### TDATA папки: `/opt/tg_sender/accounts/*/tdata/`
### 2FA: None для всех (см. `/opt/tg_sender/accounts/*/twoFA.txt`)

---

## 6. ПРОКСИ

### MTProto прокси (для Telethon)
```
Файл: /opt/tg_sender/proxy.conf
Содержимое: 94.130.191.53:8443:dd104462821249bd7ac519130220c25d09
```

### Cloudflare Worker (для Bot API)
```
URL: https://imatch-tgproxy.stilltanvoid.workers.dev/bot
Файл: /opt/tg_sender/.env (BOT_API_BASE_URL)
```

---

## 7. БАЗА ДАННЫХ

### SQLite: `/opt/tg_sender/data/sender.db`

### Таблицы
| Таблица | Назначение |
|---------|------------|
| `users` | Пользователи веб-интерфейса |
| `tg_accounts` | Telegram аккаунты |
| `contacts` | Контакты для рассылки |
| `message_templates` | Шаблоны сообщений |
| `campaigns` | Рассылки |
| `message_log` | Лог отправок |

### Текущие данные
- Контактов: 51 (группа recruiters)
- Аккаунтов: 4 (3 активных)
- Шаблонов: 1

---

## 8. ОСНОВНЫЕ КОМАНДЫ

```bash
# Подключение
ssh -i ~/.ssh/agent2_key agent2@158.160.6.22

# Статус сервисов
systemctl list-units --type=service --state=running | grep -E 'imatch|tg-sender'

# Рестарт веб-дашборда
sudo systemctl restart tg-sender-web

# Логи
sudo journalctl -u tg-sender-web -f

# Запуск мониторинга (вручную)
cd /opt/tg_sender && nohup venv/bin/python web/tg_monitor_web.py &

# Проверка базы
cd /opt/tg_sender && source venv/bin/activate
python3 -c "from core import db; db.init_db(); print(db.get_statistics())"

# Git push (из локальной папки)
cd /home/user/tg_sender
git add -A && git commit -m "msg" && git push origin main
```

---

## 9. ИЗВЕСТНЫЕ ПРОБЛЕМЫ

1. **RustDesk не подключается** — .deb версия перезаписывает конфиг. Не критично.
2. **4-й аккаунт не авторизован** — нужна повторная авторизация через Telethon.
3. **Telegram API заблокирован** — всё идёт через MTProto прокси.
4. **Мониторинг на 8088** — запускается вручную, не сервис.

---

## 10. АНТИ-СПАМ СИСТЕМА

Реализовано в `web/sender_engine.py`:
- Spintax (`{вариант1|вариант2}`)
- Умные задержки (2-10 мин)
- Дневные лимиты по возрасту аккаунта
- Нет ссылок в первом ЛС
- Окно отправки 9:00-22:00
- Ротация аккаунтов при flood

Документация: `docs/TELEGRAM_SPAM_BYPASS.md`

---

## 11. ВЕБ-ИНТЕРФЕЙС

### Страницы
| Путь | Описание |
|------|----------|
| `/` | Редирект на дашборд |
| `/dashboard` | Дашборд со статистикой |
| `/accounts` | Управление Telegram аккаунтами |
| `/contacts` | Контакты (импорт, статусы) |
| `/templates` | Шаблоны сообщений (spintax) |
| `/campaigns` | Рассылки |
| `/campaigns/new` | Создание рассылки |
| `/analytics` | Аналитика |
| `/settings` | Настройки + управление пользователями |
| `/tg` | **Telegram Web клиент** (просмотр чатов) |
| `/logs` | Журнал действий |

### API
| Путь | Метод | Описание |
|------|-------|----------|
| `/api/tg/{phone}/dialogs` | GET | Список чатов аккаунта |
| `/api/tg/{phone}/messages/{id}` | GET | Сообщения чата |
| `/api/tg/{phone}/send/{id}` | POST | Отправить сообщение |
| `/api/tg/{phone}/read/{id}` | POST | Отметить прочитанным |
| `/export/contacts` | GET | Экспорт контактов в CSV |

---

## 12. ЧТО НУЖНО ДОДЕЛАТЬ

1. Добавить больше контактов (сейчас 51)
2. Создать несколько шаблонов с spintax
3. Протестировать рассылку на малой группе
4. Добавить SSL (HTTPS) через Caddy
5. Сделать мониторинг сервисом systemd
6. Авторизовать 4-й аккаунт
