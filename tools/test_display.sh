#!/bin/bash
export DISPLAY=:99
pkill -f chromium 2>/dev/null
pkill -f epiphany 2>/dev/null
sleep 1
xterm -geometry 100x30+50+50 -bg white -fg black &
sleep 3
echo "Windows:"
xdotool search --name '' 2>/dev/null
