#!/bin/bash
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
WEB="http://127.0.0.1:18080/api/status"
URL="http://127.0.0.1:18080/web/mask-editor/"

# The web UI starts the local model server itself, using the 4-bit / 8-bit choice saved from the
# page (default: chosen by installed models and total memory). The page shows loading progress.

# After an update, a web server that is still running would keep serving the old server.py
# (security checks, model management). Compare its code fingerprint with the file on disk and
# restart it when they differ. The model server keeps running either way.
STATUS="$(curl -fsS -m 5 "$WEB" 2>/dev/null || true)"
if [ -n "$STATUS" ]; then
  DISK_VERSION="$(shasum -a 256 "$ROOT/web/mask-editor/server.py" | cut -c1-12)"
  read -r RUNNING_VERSION RUNNING_STATE < <(printf '%s' "$STATUS" | python3 -c 'import sys,json
d=json.load(sys.stdin); phase=(d.get("model") or {}).get("phase"); busy=d.get("busy") or phase=="switching"; print(d.get("server_version") or "old", "busy" if busy else "idle")' 2>/dev/null || echo "unknown idle")
  if [ "$RUNNING_VERSION" != "$DISK_VERSION" ]; then
    if [ "$RUNNING_STATE" = "busy" ]; then
      echo "检测到新版 server.py，但当前有生成 / AI 编辑任务或模型切换正在运行；完成后再双击启动一次即可更新。"
    else
      echo "检测到新版 server.py，正在重启 Web 服务（模型保持运行）..."
      pkill -f "web/mask-editor/server.py" 2>/dev/null || true
      for i in {1..20}; do
        lsof -tiTCP:18080 -sTCP:LISTEN >/dev/null 2>&1 || break
        sleep 0.3
      done
      STATUS=""
    fi
  fi
fi

if [ -z "$STATUS" ]; then
  echo "Starting Image MLX Lab..."
  cd "$ROOT"
  nohup python3 web/mask-editor/server.py >"$ROOT/web/mask-editor/server.log" 2>&1 &
  for i in {1..30}; do
    curl -fsS -m 2 "$WEB" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

if curl -fsS -m 5 "$WEB" >/dev/null 2>&1; then
  echo "Image MLX Lab is ready. 模型在后台加载；页面右上角可查看状态、切换 4-bit / 8-bit。"
  open "$URL"
  exit 0
fi

echo "Web UI did not start. See web/mask-editor/server.log"
read -n 1 -s -r -p "Press any key to close..."
