#!/usr/bin/env python3
"""Fetch only Qwen-Image-2.1's Qwen3-VL visual tower from the official BF16 shard.

The official text_encoder shard is ~5 GB, but all model.visual.* tensors are one
contiguous ~1.10 GB byte range. This script reads the safetensors header, fetches
only that range, and repacks it as a standalone safetensors file that mlx-serve
can load alongside the quantized language-model shards.
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_MODEL = Path.home() / "Documents/AI-Models/image/qwen-image-2.1-mlx-8bit"
SOURCE_REV = "790c92633540aa0cb11d9abf19eb46d861714758"
SOURCE_URL = (
    "https://huggingface.co/Qwen/Qwen-Image-2.1/resolve/"
    + SOURCE_REV
    + "/text_encoder/model-00001-of-00004.safetensors"
)


def get_range(url: str, start: int, end: int, timeout: int = 120):
    req = urllib.request.Request(
        url,
        headers={
            "Range": f"bytes={start}-{end}",
            "User-Agent": "qwen-image-2.1-mlxserve-edit-vision/1.0",
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)


def read_header(url: str):
    with get_range(url, 0, 7) as r:
        first = r.read()
    if len(first) != 8:
        raise RuntimeError(f"expected 8-byte safetensors prefix, got {len(first)}")
    header_len = struct.unpack("<Q", first)[0]
    with get_range(url, 8, 8 + header_len - 1) as r:
        raw = r.read()
    if len(raw) != header_len:
        raise RuntimeError(f"expected {header_len} header bytes, got {len(raw)}")
    return header_len, json.loads(raw)


def build_visual_header(meta: dict):
    entries = []
    for key, info in meta.items():
        if key == "__metadata__" or not key.startswith("model.visual."):
            continue
        a, b = info["data_offsets"]
        entries.append((a, b, key, info))
    if not entries:
        raise RuntimeError("no model.visual.* tensors found")
    entries.sort()
    start, end = entries[0][0], entries[-1][1]
    cursor = start
    for a, b, key, _ in entries:
        if a != cursor:
            raise RuntimeError(f"visual tensors are not contiguous before {key}: {cursor} != {a}")
        cursor = b

    out = {}
    if "__metadata__" in meta:
        out["__metadata__"] = dict(meta["__metadata__"])
    out["__metadata__"] = {
        **out.get("__metadata__", {}),
        "source_model": "Qwen/Qwen-Image-2.1",
        "source_revision": SOURCE_REV,
        "subset": "model.visual.*",
    }
    for a, b, key, info in entries:
        item = dict(info)
        item["data_offsets"] = [a - start, b - start]
        out[key] = item

    raw = json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    padded_len = (len(raw) + 7) // 8 * 8
    raw += b" " * (padded_len - len(raw))
    return start, end, len(entries), raw


def validate(path: Path):
    with path.open("rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        meta = json.loads(f.read(n))
    keys = [k for k in meta if k != "__metadata__"]
    if len(keys) != 351 or not all(k.startswith("model.visual.") for k in keys):
        raise RuntimeError(f"unexpected repack contents: {len(keys)} tensors")
    size = path.stat().st_size
    expected = 8 + n + max(meta[k]["data_offsets"][1] for k in keys)
    if size != expected:
        raise RuntimeError(f"size mismatch: file={size}, expected={expected}")
    return len(keys), size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = args.model_dir / "text_encoder" / "qwen21_visual.safetensors"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        n, size = validate(out)
        print(f"already ready: {out} ({n} tensors, {size / 1024**3:.2f} GiB)")
        return 0

    print("reading official safetensors header...")
    header_len, meta = read_header(SOURCE_URL)
    start, end, count, new_header = build_visual_header(meta)
    source_data_start = 8 + header_len
    byte_start = source_data_start + start
    byte_end = source_data_start + end - 1
    total = end - start
    print(f"visual tensors: {count}")
    print(f"downloading only visual byte range: {total / 1024**3:.2f} GiB")

    fd, tmp_name = tempfile.mkstemp(prefix=out.name + ".", suffix=".part", dir=out.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with tmp.open("wb") as f:
            f.write(struct.pack("<Q", len(new_header)))
            f.write(new_header)
            done = 0
            with get_range(SOURCE_URL, byte_start, byte_end, timeout=300) as r:
                while True:
                    chunk = r.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    pct = done * 100.0 / total
                    print(f"\r{done / 1024**2:8.1f} / {total / 1024**2:8.1f} MiB  {pct:5.1f}%", end="", flush=True)
            print()
        if done != total:
            raise RuntimeError(f"range download truncated: {done} != {total}")
        os.replace(tmp, out)
        n, size = validate(out)
        print(f"ready: {out}")
        print(f"{n} visual tensors, {size / 1024**3:.2f} GiB")
    finally:
        if tmp.exists():
            tmp.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
