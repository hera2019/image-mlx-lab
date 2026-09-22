#!/bin/bash
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
QWEN="http://127.0.0.1:11234/health"
WEB="http://127.0.0.1:18080/api/status"

mkdir -p "$HOME/.mlx-serve/logs"

if ! curl -fsS -m 2 "$QWEN" >/dev/null 2>&1; then
  echo "Starting Image MLX Lab model server..."
  nohup "$ROOT/scripts/start_server.sh" 8bit force >"$HOME/.mlx-serve/logs/image-mlx-lab-model.log" 2>&1 &
fi

if ! curl -fsS -m 2 "$WEB" >/dev/null 2>&1; then
  echo "Starting Image MLX Lab web UI..."
  cd "$ROOT"
  nohup python3 web/mask-editor/server.py >"$ROOT/web/mask-editor/server.log" 2>&1 &
fi

for i in {1..40}; do
  if curl -fsS -m 2 "$QWEN" >/dev/null 2>&1 && curl -fsS -m 2 "$WEB" >/dev/null 2>&1; then
    echo "Image MLX Lab is ready."
    open "http://127.0.0.1:18080/web/mask-editor/"
    exit 0
  fi
  sleep 1
done

echo "Services are still starting. Refresh the browser shortly."
read -n 1 -s -r -p "Press any key to close..."
