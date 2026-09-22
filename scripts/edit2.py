#!/usr/bin/env python3
import argparse
import base64
import json
import urllib.error
from datetime import datetime
from pathlib import Path

from generate import choose_model, request_json, slug

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results/edit2"


def main():
    ap = argparse.ArgumentParser(description="Qwen-Image-2.1 真正的 image-conditioned Edit")
    ap.add_argument("--image", type=Path, required=True, help="主参考图 PNG/JPEG")
    ap.add_argument("--ref-image", type=Path, action="append", default=[], help="额外参考图，可重复传入")
    ap.add_argument("--prompt", required=True, help="编辑指令，可直接使用中文")
    ap.add_argument("--size", default=None, help='可选，如 "768x576"；默认保持主参考图比例/尺寸')
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model")
    ap.add_argument("--server", default="http://127.0.0.1:11234")
    args = ap.parse_args()

    if not args.image.is_file():
        raise SystemExit(f"主参考图不存在：{args.image}")
    for p in args.ref_image:
        if not p.is_file():
            raise SystemExit(f"额外参考图不存在：{p}")

    base = args.server.rstrip("/")
    model = choose_model(base, args.model)
    payload = {
        "model": model,
        "prompt": args.prompt,
        "mode": "edit",
        "image": base64.b64encode(args.image.read_bytes()).decode("ascii"),
        "steps": args.steps,
        "seed": args.seed,
    }
    if args.size:
        payload["size"] = args.size
    if args.ref_image:
        payload["ref_images"] = [
            base64.b64encode(p.read_bytes()).decode("ascii") for p in args.ref_image
        ]

    print(f"model: {model}", flush=True)
    print(f"source: {args.image}", flush=True)
    print(f"refs: {len(args.ref_image)}  steps={args.steps} seed={args.seed}", flush=True)
    print(f"prompt: {args.prompt}", flush=True)
    try:
        result = request_json(base + "/v1/images/generations", payload, timeout=7200)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"服务器返回 HTTP {e.code}:\n{body[:5000]}")

    try:
        encoded = result["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError):
        raise SystemExit("服务器返回格式异常：\n" + json.dumps(result, ensure_ascii=False)[:3000])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out = OUT_DIR / f"{args.image.stem}_EDIT_{slug(args.prompt, 20)}_{stamp}.png"
    out.write_bytes(base64.b64decode(encoded))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
