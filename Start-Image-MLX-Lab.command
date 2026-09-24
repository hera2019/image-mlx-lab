#!/bin/bash
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
WEB="http://127.0.0.1:18080/api/status"
URL="http://127.0.0.1:18080/web/mask-editor/"

# The web UI starts the local model server itself, using the 4-bit / 8-bit choice saved from the
# page (default: chosen by installed models and total memory). The page shows loading progress.
if ! curl -fsS -m 2 "$WEB" >/dev/null 2>&1; then
  echo "Starting Image MLX Lab..."
  cd "$ROOT"
  nohup python3 web/mask-editor/server.py >"$ROOT/web/mask-editor/server.log" 2>&1 &
  for i in {1..30}; do
    curl -fsS -m 2 "$WEB" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

if curl -fsS -m 2 "$WEB" >/dev/null 2>&1; then
  echo "Image MLX Lab is ready. 模型在后台加载；页面右上角可查看状态、切换 4-bit / 8-bit。"
  open "$URL"
  exit 0
fi

echo "Web UI did not start. See web/mask-editor/server.log"
read -n 1 -s -r -p "Press any key to close..."
