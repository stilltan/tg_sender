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

## 2. Тесты (уже написаны, 8 штук)

```bash
# Скопировать тесты во временную папку (НЕ в /opt — тесты подменяют путь БД)
mkdir -p /tmp/tg_sender_tests/web
cp /opt/tg_sender/tests/test_tg_sender.py /tmp/tg_sender_tests/
cp /opt/tg_sender/web/app.py /opt/tg_sender/web/sender_engine.py /tmp/tg_sender_tests/web/
cd /tmp/tg_sender_tests
/opt/tg_sender/venv/bin/python -m unittest test_tg_sender -v
# В конце должно быть: Ran 8 tests ... OK
```

**Важно:** тесты работают с КОПИЕЙ БД во временной папке — боевую БД не трогают. Никогда не запускай их из `/opt/tg_sender` с боевой БД.

Что покрыто: миграция старой схемы (колонки добавляются, данные не теряются, повторный прогон безопасен), `log_message` пишет `account_id`, запрос статистики аккаунтов работает, `hash/verify_password`, `init_db` на свежей БД, `get_contacts_for_campaign`.

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

- [ ] Тесты прогнаны и дали OK
- [ ] Служба active, ошибок в логах нет
- [ ] Бэкап сделан (файлы/БД)
- [ ] Секреты не засветились (sessions/, accounts/, .admin_credentials, .env)
- [ ] Изменение закоммичено: `cd /opt/tg_sender && sudo -u agent2 git add -A && sudo -u agent2 git commit -m "..."` (данные и секреты игнорируются .gitignore)
- [ ] Владельцу дан отчёт: «Готово. Сделал: … Проверил: …»
