#!/usr/bin/env bash
# =============================================================================
# Добавление SSH ключа для удалённого управления
# Запустите этот скрипт на сервере после первого подключения
# =============================================================================

SSH_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMpnXVxYGwEDBotdno/EpIb9UV+ZyBKDGDEd+SQQFJTq imatch-agent"

echo "Добавление SSH ключа..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh

if ! grep -q "imatch-agent" ~/.ssh/authorized_keys 2>/dev/null; then
    echo "$SSH_KEY" >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
    echo "✅ SSH ключ добавлен"
else
    echo "ℹ️ SSH ключ уже существует"
fi

echo ""
echo "Теперь вы можете подключиться удалённо:"
echo "  ssh ubuntu@$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')"
