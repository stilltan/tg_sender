# TG Sender — чек-лист работы агента (AGENT CHECKLIST)
> Как тестировать и деплоить без ошибок. Прочитай перед ЛЮБОЙ правкой.

## 1. Перед изменением кода

1. Прочитай `AGENT_HANDOFF.md` — там текущее состояние сервера.
2. Сделай бэкап того, что меняешь:
   ```bash
   cd /opt/tg_sender
   sudo cp web/app.py web/app.py.bak_$(date +%Y%m%d_%H%M%S)
   ```
3. Сделай бэкап БД (перед миграциями/рассылками):
   ```bash
   sudo cp data/sender.db backups/sender_$(date +%Y%m%d_%H%M%S).db.bak
   ```

## 2. Тесты (уже написаны, 13 штук)

```bash
# Скопировать тесты во временную папку (НЕ в /opt — тесты подменяют путь БД)
mkdir -p /tmp/tg_sender_tests/web
cp /opt/tg_sender/tests/test_tg_sender.py /tmp/tg_sender_tests/
cp /opt/tg_sender/web/app.py /opt/tg_sender/web/sender_engine.py /tmp/tg_sender_tests/web/
cd /tmp/tg_sender_tests
/opt/tg_sender/venv/bin/python -m unittest test_tg_sender -v
# В конце должно быть: Ran 13 tests ... OK
```

**Важно:** тесты работают с КОПИЕЙ БД во временной папке — боевую БД не трогают. Никогда не запускай их из `/opt/tg_sender` с боевой БД.

Что покрыто: миграция старой схемы (колонки добавляются, данные не теряются, повторный прогон безопасен), `log_message` пишет `account_id`, запрос статистики аккаунтов работает, `hash/verify_password`, `init_db` на свежей БД, `get_contacts_for_campaign`, журнал действий (`log_action`/`admin_log_list`), лимит неудачных входов, IP-фильтр, `client_ip` с X-Forwarded-For, наличие таблицы `admin_log`.

### Как мы тестируем (принципы, которые нельзя нарушать)

1. **Тесты пофайлово, не всё разом.** Если тесты делят одну БД/файлы — запуск всего в одном процессе падает («database is locked», «no such table»). Всегда запускай один тест-файл за раз.
2. **Тестируй на копии, не на боевом.** Тесты подменяют `DB_PATH` на временный файл. Боевую БД не трогаем.
3. **Не выдумывай — проверяй по-живому.** После деплоя обязательно: `curl` к страницам, реальный вход с верным/неверным паролем, проверка записи в журнале, `systemctl is-active`, лог без traceback.
4. **Сверяй контрольные суммы.** После установки: `md5sum` локального и серверного файла должны совпадать.
5. **Перед ответом «готово» перечитай свой код** и проверь соседние функции — не сломал ли ты что-то рядом.
6. **Добавляй тест на каждый баг.** Нашёл ошибку → сначала напиши тест, который её ловит, потом чини. Так ошибка не вернётся.

## 3. Правки → установка → перезапуск

```bash
cd /opt/tg_sender
# после правки файла (например web/app.py):
sudo install -m 0664 -o agent2 -g agent2 web/app.py web/app.py
sudo systemctl restart tg-sender-web
sleep 2
systemctl is-active tg-sender-web          # → active
# проверить логи на ошибки:
sudo journalctl -u tg-sender-web -n 30 --no-pager | grep -iE 'error|traceback' || echo 'ошибок нет'
# проверить страницы:
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/login   # → 200
```

## 4. Если менял схему БД

- `web/app.py` содержит `migrate_db()` — при рестарте службы колонки добавятся автоматически.
- После рестарта проверь схему:
  ```bash
  /opt/tg_sender/venv/bin/python -c "import sqlite3; c=sqlite3.connect('file:/opt/tg_sender/data/sender.db?mode=ro',uri=True); print([r[1] for r in c.execute('PRAGMA table_info(message_log)')])"
  ```

## 5. Рассылки (отвечаешь за реальные сообщения людям!)

1. Сначала **тестовое сообщение** — кнопка в дашборде или `tools/send_test.py`.
2. Проверь, что аккаунты активны: `tools/test_all_accounts.py` (читает статусы, ничего не шлёт).
3. Начинай с **маленькой группы** контактов и **больших задержек** (delay 60–120 с).
4. Следи за флуд-лимитами: ошибки `FLOOD_WAIT` — это норма, движок сам ждёт и переключает аккаунты.
5. Не гоняй кампании чаще, чем нужно — это риск бана аккаунтов.

## 6. Перед ответом «готово» (самопроверка)

- [ ] Тесты прогнаны пофайлово и дали OK (13/13)
- [ ] Служба active, ошибок в логах нет (`journalctl | grep -i error`)
- [ ] Страницы отвечают по-живому (curl /login → 200, /logs → 302 без сессии)
- [ ] Вход с верным паролем → 302, с неверным → страница ошибки + запись `login_fail` в журнале
- [ ] md5 локального и серверного файла совпадают
- [ ] Бэкап сделан (файлы/БД) перед изменением
- [ ] Секреты не засветились (sessions/, accounts/, .admin_credentials, .env, TG_SENDER_SECRET_KEY)
- [ ] Изменение закоммичено: `cd /opt/tg_sender && sudo -u agent2 git add -A && sudo -u agent2 git commit -m "..."` (данные и секреты игнорируются .gitignore)
- [ ] Владельцу дан отчёт: «Готово. Сделал: … Проверил: …»
