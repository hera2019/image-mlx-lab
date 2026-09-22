#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/worktrees/mlx-serve/zig-out/bin/mlx-serve"
VARIANT="${1:-4bit}"
MODE="${2:-safe}"
case "$VARIANT" in
  4bit) MODEL_DIR="$HOME/Documents/AI-Models/image/qwen-image-2.1-mlx-4bit" ;;
  8bit) MODEL_DIR="$HOME/Documents/AI-Models/image/qwen-image-2.1-mlx-8bit" ;;
  *) echo "用法: $0 [4bit|8bit] [safe|force]" >&2; exit 1 ;;
esac
case "$MODE" in
  safe|force) ;;
  *) echo "用法: $0 [4bit|8bit] [safe|force]" >&2; exit 1 ;;
esac
PORT="${PORT:-11234}"

if [[ ! -x "$BIN" ]]; then
  echo "mlx-serve 未构建，请先运行 setup_model.py" >&2
  exit 2
fi
if [[ ! -d "$MODEL_DIR" ]]; then
  echo "模型目录不存在：$MODEL_DIR" >&2
  exit 3
fi

if [[ "$MODE" == "force" ]]; then
  exec "$BIN" \
    --model "$MODEL_DIR" \
    --serve \
    --host 127.0.0.1 \
    --port "$PORT" \
    --log-level info \
    --skip-mem-preflight
else
  exec "$BIN" \
    --model "$MODEL_DIR" \
    --serve \
    --host 127.0.0.1 \
    --port "$PORT" \
    --log-level info
fi
