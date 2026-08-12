#!/usr/bin/env bash
# =============================================================================
# TG Sender — автонастройка VPS (Ubuntu/Debian)
#
# Что делает:
#   1) ставит пакеты (python3-venv, git)
#   2) клонирует репозиторий tg_sender
#   3) создаёт .env с вашими настройками
#   4) создаёт venv и ставит зависимости
#   5) создаёт systemd-службу для бота
#   6) запускает бота
#
# Запуск:
#   sudo bash deploy_tg_sender.sh
# =============================================================================

set -euo pipefail

# ============= НАСТРОЙКИ =============
REPO_URL="https://github.com/stilltan/tg_sender.git"
INSTALL_DIR="/opt/tg_sender"
BOT_TOKEN="8998492187:AAG7o3sGamESyZJpCs9njSXfMKSUTMVSkcI"
SUPER_ADMIN_ID="7627878199"
SERVICE_NAME="tg-sender"
# =====================================

log()  { echo -e "\e[1;36m==>\e[0m $*"; }
warn() { echo -e "\e[1;33m[!]\e[0m $*"; }
err()  { echo -e "\e[1;31m[ОШИБКА]\e[0m $*" >&2; }

[[ $EUID -ne 0 ]] && { err "Запустите от root: sudo bash $0"; exit 1; }

echo "══════════════════════════════════════════════"
echo "  TG Sender — автонастройка VPS"
echo "  Каталог: $INSTALL_DIR"
echo "══════════════════════════════════════════════"

# ---------- 1. пакеты ----------
log "1/6 Установка пакетов"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl

# ---------- 2. клонирование ----------
log "2/6 Клонирование репозитория"
if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Репозиторий уже существует, обновляю..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ---------- 3. .env ----------
log "3/6 Создание .env"
cat > "$INSTALL_DIR/.env" << EOF
# Telegram Bot Settings
BOT_TOKEN=$BOT_TOKEN
SUPER_ADMIN_ID=$SUPER_ADMIN_ID
ADMIN_GROUP_ID=
EOF

log ".env создан с токеном бота"

# ---------- 4. venv и зависимости ----------
log "4/6 Создание виртуального окружения"
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

log "Установка зависимостей"
pip install --upgrade pip
pip install -r "$INSTALL_DIR/requirements.txt"

# Создаём папку данных
mkdir -p "$INSTALL_DIR/data"

# ---------- 5. systemd сервис ----------
log "5/6 Создание systemd сервиса"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=TG Sender Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$INSTALL_DIR/venv/bin/python -m bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# ---------- 6. запуск ----------
log "6/6 Запуск бота"
systemctl start "$SERVICE_NAME"

sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  ✅ Бот успешно запущен!"
    echo "══════════════════════════════════════════════"
    echo ""
    echo "  Сервис: $SERVICE_NAME"
    echo "  Статус: $(systemctl is-active $SERVICE_NAME)"
    echo ""
    echo "  Полезные команды:"
    echo "    Статус:   systemctl status $SERVICE_NAME"
    echo "    Логи:     journalctl -u $SERVICE_NAME -f"
    echo "    Рестарт:  systemctl restart $SERVICE_NAME"
    echo "    Стоп:     systemctl stop $SERVICE_NAME"
    echo ""
    echo "  Бот: @Cursdworld"
    echo "  Админ ID: $SUPER_ADMIN_ID"
    echo ""
    echo "  Откройте Telegram и отправьте /start боту"
    echo "══════════════════════════════════════════════"
else
    err "Бот не запустился. Проверьте логи:"
    echo "  journalctl -u $SERVICE_NAME -n 50"
fi
