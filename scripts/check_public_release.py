#!/usr/bin/env python3
"""Preflight guard for publishing Image MLX Lab."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PARTS = {
    "results",
    ".venv",
    "venv",
    "worktrees",
    "__pycache__",
    "backups",
    "node_modules",
    ".zig-cache",
    "zig-out",
    ".zig-toolchain",
}
FORBIDDEN_SUFFIXES = {
    ".safetensors", ".gguf", ".ckpt", ".pth", ".pt", ".onnx", ".bin",
    ".log", ".pid", ".tmp", ".temp", ".cache",
}
PREVIEW_RE = re.compile(r"preview.*\.(png|jpe?g|webp)$", re.I)
ABS_USER_RE = re.compile(r"/Users/[^/\s]+/")
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)

def git_candidates() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return [ROOT / line for line in out.splitlines() if line.strip()]
    except Exception:
        return [p for p in ROOT.rglob("*") if p.is_file()]

def history_paths() -> list[str]:
    """Every path that ever existed in any commit: publishing the repo publishes its history too."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "--all", "--pretty=format:", "--name-only"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return sorted({line for line in out.splitlines() if line.strip()})
    except Exception:
        return []

def forbidden_reason(rel: Path) -> str | None:
    if set(rel.parts) & FORBIDDEN_PARTS:
        return "FORBIDDEN PATH"
    if rel.suffix.lower() in FORBIDDEN_SUFFIXES or PREVIEW_RE.search(rel.name):
        return "FORBIDDEN ARTIFACT"
    if rel.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}:
        return "REVIEW IMAGE"
    return None

def main() -> int:
    problems: list[str] = []
    public: list[str] = []

    for name in history_paths():
        reason = forbidden_reason(Path(name))
        if reason:
            problems.append(f"{reason} (in Git history): {name}")

    for p in git_candidates():
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            continue
        parts = set(rel.parts)
        if parts & FORBIDDEN_PARTS:
            problems.append(f"FORBIDDEN PATH: {rel}")
            continue
        if p.suffix.lower() in FORBIDDEN_SUFFIXES or PREVIEW_RE.search(p.name):
            problems.append(f"FORBIDDEN ARTIFACT: {rel}")
            continue

        public.append(str(rel))
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}:
            problems.append(f"REVIEW IMAGE: {rel}")
            continue

        if p.stat().st_size <= 2_000_000:
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:
                continue
            if rel.as_posix() != "scripts/check_public_release.py" and ABS_USER_RE.search(txt):
                problems.append(f"ABSOLUTE USER PATH: {rel}")
            if SECRET_RE.search(txt):
                problems.append(f"POSSIBLE SECRET: {rel}")

    print(f"Image MLX Lab public-release preflight")
    print(f"Root: {ROOT}")
    print(f"Candidate public files: {len(public)}")
    if problems:
        print("\nReview required:")
        for x in problems:
            print(" -", x)
        return 1

    print("\nPASS: no forbidden local artifacts or obvious secrets were found in Git candidates.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
