#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "qwen-image-2.1-mlx-4bit": {
        "repo": "ddalcu/Qwen-Image-2.1-MLX-Serve-4bit",
        "revision": "88eb1b3bb5591ed59b68a6e1a1c2d9baade73e38",
        "dir": Path.home() / "Documents/AI-Models/image/qwen-image-2.1-mlx-4bit",
    },
    "qwen-image-2.1-mlx-8bit": {
        "repo": "ddalcu/Qwen-Image-2.1-MLX-Serve-8bit",
        "revision": "fbda4caa0b4b1e17b5a29633e8deb600386f1eaf",
        "dir": Path.home() / "Documents/AI-Models/image/qwen-image-2.1-mlx-8bit",
    },
}
RUNTIME_DIR = ROOT / "worktrees/mlx-serve"
RUNTIME_REPO = "https://github.com/ddalcu/mlx-serve.git"
RUNTIME_BRANCH = "feat/qwen-image-2.1"
RUNTIME_REVISION = "c7c2cc5b3d160ecac2ad16b00d4feedfc6ce5e93"
ZIG_VERSION = "0.17.0-dev.2248+3f6a02acd"
STATE_FILE = ROOT / "results/setup-state.json"
RUNTIME_PATCH = ROOT / "patches/qwen-image-2.1-true-edit-mlx.patch"
EDIT_VISION_SCRIPT = ROOT / "scripts/fetch_edit_vision.py"


def run(cmd, cwd=None):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def tree_size(path):
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def ensure_space(spec):
    model_dir = spec["dir"]
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    if tree_size(model_dir) > 1024**3:
        return
    free = shutil.disk_usage(model_dir.parent).free
    if free < 24 * 1024**3:
        raise SystemExit(
            f"可用空间只有 {free / 1024**3:.1f} GiB；"
            "首次下载建议至少保留 24 GiB。"
        )


def download_model(spec):
    from huggingface_hub import snapshot_download

    ensure_space(spec)
    print(f"模型仓库: {spec['repo']}@{spec['revision']}", flush=True)
    path = snapshot_download(
        repo_id=spec["repo"],
        revision=spec["revision"],
        local_dir=spec["dir"],
    )
    return spec["revision"], Path(path)


def edit_vision_ready(spec):
    return (spec["dir"] / "text_encoder/qwen21_visual.safetensors").is_file()


def want_edit_vision(choice):
    """指令编辑 / AI 局部编辑需要的视觉模块是可选的：参数指定就照做，否则在终端里询问。"""
    if choice is not None:
        return choice
    if not sys.stdin.isatty():
        print("未指定 --edit-vision / --skip-edit-vision，且不是交互终端：跳过编辑用视觉模块。")
        return False
    print("\n编辑用视觉模块（约 1.1 GB）：“指令编辑”和“AI 局部编辑”需要它；")
    print("只用文生图、图生图和普通图片编辑可以不装，以后随时可以补装。")
    answer = input("现在下载吗？[y/N] ").strip().lower()
    return answer in {"y", "yes", "是"}


def ensure_edit_vision(spec, choice):
    if edit_vision_ready(spec):
        print("编辑用视觉模块已存在。", flush=True)
        return
    if want_edit_vision(choice):
        run([sys.executable, str(EDIT_VISION_SCRIPT), "--model-dir", str(spec["dir"])])
    else:
        print("已跳过编辑用视觉模块。以后需要时运行：")
        print(f"  .venv/bin/python scripts/fetch_edit_vision.py --model-dir {spec['dir']}")


def ensure_runtime_patch():
    if not RUNTIME_PATCH.is_file():
        raise SystemExit(f"缺少运行时补丁: {RUNTIME_PATCH}")

    reverse = subprocess.run(
        ["git", "apply", "--reverse", "--check", str(RUNTIME_PATCH)],
        cwd=RUNTIME_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if reverse.returncode == 0:
        print(f"运行时补丁已存在: {RUNTIME_PATCH.name}", flush=True)
        return False

    check = subprocess.run(
        ["git", "apply", "--check", str(RUNTIME_PATCH)],
        cwd=RUNTIME_DIR,
    )
    if check.returncode != 0:
        raise SystemExit(
            "mlx-serve 固定版本与补丁不匹配；为避免构建错误，已停止。"
        )

    run(["git", "apply", str(RUNTIME_PATCH)], cwd=RUNTIME_DIR)
    print(f"已应用运行时补丁: {RUNTIME_PATCH.name}", flush=True)
    return True


def prepare_runtime():
    valid = False
    if (RUNTIME_DIR / ".git").is_dir():
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=RUNTIME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        valid = probe.returncode == 0
    if not valid:
        if RUNTIME_DIR.exists():
            shutil.rmtree(RUNTIME_DIR)
        RUNTIME_DIR.parent.mkdir(parents=True, exist_ok=True)
        run([
            "git", "clone", "--depth", "1", "--single-branch",
            "--branch", RUNTIME_BRANCH, RUNTIME_REPO, str(RUNTIME_DIR),
        ])
    run(["git", "fetch", "--depth", "1", "origin", RUNTIME_REVISION], cwd=RUNTIME_DIR)
    run(["git", "checkout", "--detach", RUNTIME_REVISION], cwd=RUNTIME_DIR)
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=RUNTIME_DIR)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=RUNTIME_DIR, text=True
    ).strip()

    patch_applied_now = ensure_runtime_patch()

    binary = RUNTIME_DIR / "zig-out/bin/mlx-serve"
    if patch_applied_now and binary.is_file():
        binary.unlink()
    if not binary.is_file():
        run(["env", f"ZIG_VERSION={ZIG_VERSION}", "./scripts/fetch-zig.sh"], cwd=RUNTIME_DIR)
        run(["./scripts/build-mlx.sh"], cwd=RUNTIME_DIR)
        run(["./scripts/fetch-llama.sh"], cwd=RUNTIME_DIR)
        run([
            str(RUNTIME_DIR / ".zig-toolchain/zig"),
            "build", "-Doptimize=ReleaseFast",
        ], cwd=RUNTIME_DIR)
    if not binary.is_file():
        raise SystemExit("mlx-serve 构建完成后仍未找到二进制文件。")
    return commit, binary


def save_state(model_key, spec, model_sha, runtime_commit, binary):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "model": model_key,
        "model_repo": None if spec is None else spec["repo"],
        "model_revision": model_sha,
        "model_dir": None if spec is None else str(spec["dir"]),
        "model_bytes": 0 if spec is None else tree_size(spec["dir"]),
        "runtime_repo": RUNTIME_REPO,
        "runtime_branch": RUNTIME_BRANCH,
        "runtime_commit": runtime_commit,
        "runtime_binary": None if binary is None else str(binary),
    }
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--model",
        choices=sorted(MODELS),
        default="qwen-image-2.1-mlx-4bit",
    )
    ap.add_argument("--download-only", action="store_true")
    vision = ap.add_mutually_exclusive_group()
    vision.add_argument(
        "--edit-vision", dest="edit_vision", action="store_const", const=True,
        help="同时下载编辑用视觉模块（约 1.1 GB；指令编辑 / AI 局部编辑需要）",
    )
    vision.add_argument(
        "--skip-edit-vision", dest="edit_vision", action="store_const", const=False,
        help="不下载编辑用视觉模块；不指定时会在终端里询问",
    )
    ap.add_argument(
        "--runtime-only",
        action="store_true",
        help="只构建 mlx-serve 运行环境，不下载模型",
    )
    args = ap.parse_args()

    if args.runtime_only:
        runtime_commit, binary = prepare_runtime()
        save_state(None, None, None, runtime_commit, binary)
        print("\n运行环境准备完成；没有下载模型。")
        return 0

    spec = MODELS[args.model]
    model_sha, _ = download_model(spec)
    ensure_edit_vision(spec, args.edit_vision)

    if args.download_only:
        save_state(args.model, spec, model_sha, None, None)
        return 0

    runtime_commit, binary = prepare_runtime()
    save_state(args.model, spec, model_sha, runtime_commit, binary)
    print("\n准备完成。下一步：")
    print("  双击 Start-Image-MLX-Lab.command，或运行 python3 web/mask-editor/server.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
