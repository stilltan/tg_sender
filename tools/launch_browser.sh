#!/bin/bash
export DISPLAY=:99
pkill -f epiphany 2>/dev/null
sleep 1
xsetroot -solid '#1a1a2e' 2>/dev/null
nohup epiphany 'https://web.telegram.org/' > /tmp/browser.log 2>&1 &
sleep 5
ps aux | grep epiphany | grep -v grep
