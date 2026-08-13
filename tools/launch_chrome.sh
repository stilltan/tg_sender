#!/bin/bash
export DISPLAY=:99
pkill -f epiphany 2>/dev/null
pkill -f chromium 2>/dev/null
sleep 1
xsetroot -solid '#1a1a2e' 2>/dev/null
nohup chromium --no-sandbox --disable-gpu --disable-software-rasterizer --start-maximized 'https://web.telegram.org/' > /tmp/chrome.log 2>&1 &
sleep 10
ps aux | grep chromium | grep -v grep | head -3
echo '---'
xdotool search --name '' 2>/dev/null | head -5
