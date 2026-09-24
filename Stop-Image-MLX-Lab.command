#!/bin/bash
pkill -f "web/mask-editor/server.py" 2>/dev/null || true
for PID in $(lsof -tiTCP:11234 -sTCP:LISTEN 2>/dev/null); do
  ps -o command= -p "$PID" | grep -q "mlx-serve" && kill "$PID" 2>/dev/null
done
echo "Image MLX Lab stopped."
sleep 1
