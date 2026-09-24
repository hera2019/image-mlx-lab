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

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
# Public screenshots / demo images live only in docs/images/ and must each be listed (one file
# name per line) in docs/images/APPROVED.txt after a human has checked them. Everything else,
# and anything under results/, stays blocked.
PUBLIC_IMAGE_DIR = "docs/images"
APPROVED_LIST = ROOT / PUBLIC_IMAGE_DIR / "APPROVED.txt"
SELF = "scripts/check_public_release.py"

def approved_images() -> set[str]:
    try:
        lines = APPROVED_LIST.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return set()
    return {l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")}

def image_reason(rel: Path, approved: set[str]) -> str | None:
    if rel.suffix.lower() not in IMAGE_SUFFIXES:
        return None
    if rel.parent.as_posix() == PUBLIC_IMAGE_DIR and rel.name in approved:
        return None
    return "REVIEW IMAGE (only approved files in docs/images/ may be public)"

def forbidden_reason(rel: Path, approved: set[str]) -> str | None:
    if set(rel.parts) & FORBIDDEN_PARTS:
        return "FORBIDDEN PATH"
    if rel.suffix.lower() in FORBIDDEN_SUFFIXES or PREVIEW_RE.search(rel.name):
        return "FORBIDDEN ARTIFACT"
    return image_reason(rel, approved)

def history_text_problems() -> list[str]:
    """Scan every line ever added in any commit: old file versions are published with the history."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "--all", "-p", "--no-color", "--no-ext-diff",
             "--format=@@commit %h"],
            text=True, errors="replace", stderr=subprocess.DEVNULL,
        )
    except Exception:
        return ["COULD NOT READ Git history text"]
    problems: set[str] = set()
    commit, path = "", ""
    for line in out.splitlines():
        if line.startswith("@@commit "):
            commit = line.split()[1]
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and path and path != SELF:
            if ABS_USER_RE.search(line):
                problems.add(f"ABSOLUTE USER PATH (in Git history {commit}): {path}")
            if SECRET_RE.search(line):
                problems.add(f"POSSIBLE SECRET (in Git history {commit}): {path}")
    return sorted(problems)

def main() -> int:
    problems: list[str] = []
    public: list[str] = []
    approved = approved_images()

    for name in history_paths():
        reason = forbidden_reason(Path(name), approved)
        if reason:
            problems.append(f"{reason} (in Git history): {name}")
    problems.extend(history_text_problems())

    for p in git_candidates():
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            continue
        reason = forbidden_reason(rel, approved)
        if reason and not reason.startswith("REVIEW IMAGE"):
            problems.append(f"{reason}: {rel}")
            continue

        public.append(str(rel))
        if reason:
            problems.append(f"{reason}: {rel}")
            continue
        if rel.suffix.lower() in IMAGE_SUFFIXES:
            continue

        if p.stat().st_size <= 2_000_000:
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:
                continue
            if rel.as_posix() != SELF and ABS_USER_RE.search(txt):
                problems.append(f"ABSOLUTE USER PATH: {rel}")
            if SECRET_RE.search(txt):
                problems.append(f"POSSIBLE SECRET: {rel}")

    print(f"Image MLX Lab public-release preflight")
    print(f"Root: {ROOT}")
    print(f"Candidate public files: {len(public)}")
    print(f"Approved public images: {len(approved)}")
    if problems:
        print("\nReview required:")
        for x in problems:
            print(" -", x)
        return 1

    print("\nPASS: no forbidden artifacts, unapproved images, user paths or obvious secrets"
          " in current files or Git history.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
