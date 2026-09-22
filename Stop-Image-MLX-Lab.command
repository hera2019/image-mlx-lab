#!/bin/bash
pkill -f "web/mask-editor/server.py" 2>/dev/null || true
PID="$(lsof -tiTCP:11234 -sTCP:LISTEN 2>/dev/null || true)"
[ -n "$PID" ] && kill "$PID" 2>/dev/null || true
echo "Image MLX Lab stopped."
sleep 1
