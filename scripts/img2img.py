#!/usr/bin/env python3
import argparse
import base64
import json
import struct
import urllib.error
from datetime import datetime
from pathlib import Path

from generate import choose_model, request_json, slug

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results/img2img"


def source_size(path: Path) -> str:
    with path.open("rb") as f:
        header = f.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise SystemExit("目前自动读取尺寸只支持 PNG；非 PNG 请显式传 --size WIDTHxHEIGHT。")
    w, h = struct.unpack(">II", header[16:24])
    return f"{w}x{h}"


def main():
    ap = argparse.ArgumentParser(description="Qwen-Image-2.1 本地图生图 / variation")
    ap.add_argument("--image", type=Path, required=True, help="输入 PNG")
    ap.add_argument("--prompt", required=True, help="描述希望得到的目标图")
    ap.add_argument("--strength", type=float, default=0.45, help="0~1；越低越像原图")
    ap.add_argument("--size", default="source", help='默认 source，或如 "768x576"')
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model")
    ap.add_argument("--server", default="http://127.0.0.1:11234")
    args = ap.parse_args()

    if not args.image.is_file():
        raise SystemExit(f"输入图片不存在：{args.image}")
    if not (0 < args.strength <= 1):
        raise SystemExit("--strength 必须在 (0, 1]。")

    size = source_size(args.image) if args.size == "source" else args.size
    base = args.server.rstrip("/")
    model = choose_model(base, args.model)
    encoded_input = base64.b64encode(args.image.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "prompt": args.prompt,
        "mode": "variation",
        "image": encoded_input,
        "strength": args.strength,
        "size": size,
        "steps": args.steps,
        "seed": args.seed,
    }

    print(f"model: {model}", flush=True)
    print(f"source: {args.image}", flush=True)
    print(f"size={size} strength={args.strength} steps={args.steps} seed={args.seed}", flush=True)
    try:
        result = request_json(base + "/v1/images/generations", payload, timeout=7200)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"服务器返回 HTTP {e.code}:\n{body[:3000]}")
    try:
        encoded = result["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError):
        raise SystemExit("服务器返回格式异常：\n" + json.dumps(result, ensure_ascii=False)[:2000])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    s = int(round(args.strength * 100))
    out = OUT_DIR / f"{args.image.stem}_s{s:02d}_{slug(args.prompt, 18)}_{stamp}.png"
    out.write_bytes(base64.b64decode(encoded))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
