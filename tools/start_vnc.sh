#!/bin/bash
# Start VNC + noVNC + Telegram Web

echo "Stopping old processes..."
pkill -9 -f "Xvfb :99" 2>/dev/null
pkill -9 x11vnc 2>/dev/null
pkill -9 websockify 2>/dev/null
pkill -9 epiphany 2>/dev/null
sleep 1

echo "Starting Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 -ac &
sleep 2

export DISPLAY=:99

echo "Starting x11vnc..."
x11vnc -display :99 -forever -nopw -rfbport 5900 -bg -shared -xdamage 2>/dev/null
sleep 1

echo "Starting noVNC..."
nohup /opt/tg_sender/venv/bin/websockify --web /opt/novnc 6080 localhost:5900 > /tmp/novnc.log 2>&1 &
sleep 2

echo "Starting Telegram Web..."
nohup epiphany 'https://web.telegram.org/' > /tmp/browser.log 2>&1 &
sleep 3

echo ""
echo "=== Status ==="
ps aux | grep -E 'Xvfb|x11vnc|websock|epiphany' | grep -v grep | awk '{print $11, $12}'
echo ""
echo "=== Ports ==="
ss -tlnp | grep -E '5900|6080' | awk '{print $4}'
echo ""
echo "=== noVNC URL ==="
echo "http://158.160.6.22:6080/vnc.html"
