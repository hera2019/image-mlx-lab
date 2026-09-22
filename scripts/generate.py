#!/usr/bin/env python3
import argparse
import base64
import json
import re
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results/generated"


def request_json(url, payload=None, timeout=30):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def choose_model(base_url, requested=None):
    if requested:
        return requested
    models = request_json(base_url + "/v1/models").get("data", [])
    if not models:
        raise SystemExit("服务器在线，但 /v1/models 没有模型。")
    for item in models:
        mid = str(item.get("id", ""))
        if "qwen-image-2.1" in mid.lower():
            return mid
    return str(models[0]["id"])


def slug(text, limit=24):
    text = unicodedata.normalize("NFKC", text).strip()
    chars = []
    for ch in text:
        if ch.isalnum():
            chars.append(ch)
        elif chars and chars[-1] != "_":
            chars.append("_")
        if len(chars) >= limit:
            break
    value = "".join(chars).strip("_")
    return value or "image"


def main():
    ap = argparse.ArgumentParser(description="Qwen-Image-2.1 本地生图")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt")
    src.add_argument("--prompt-file", type=Path)
    ap.add_argument("--size", default="1024x1024")
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model")
    ap.add_argument("--server", default="http://127.0.0.1:11234")
    args = ap.parse_args()

    prompt = args.prompt
    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        raise SystemExit("提示词不能为空。")

    base = args.server.rstrip("/")
    model = choose_model(base, args.model)
    payload = {
        "model": model,
        "prompt": prompt,
        "size": args.size,
        "steps": args.steps,
        "seed": args.seed,
    }

    print("model:", model, flush=True)
    print("request:", json.dumps(payload, ensure_ascii=False), flush=True)
    result = request_json(base + "/v1/images/generations", payload, timeout=7200)
    try:
        encoded = result["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError):
        raise SystemExit("服务器返回格式异常：\n" + json.dumps(result, ensure_ascii=False)[:2000])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out = OUT_DIR / f"{slug(prompt)}_{stamp}.png"
    out.write_bytes(base64.b64decode(encoded))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
