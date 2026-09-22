# Public Release Checklist — Image MLX Lab

Before creating or pushing the public GitHub repository:

## Never publish
- `results/` — user-loaded images, generated images, masks, edited outputs, performance logs.
- `.venv/`, `worktrees/`, local runtime builds and toolchains.
- Model weights such as `*.safetensors`, `*.gguf`, `*.onnx`, `*.pth`, `*.pt`, `*.bin`.
- `web/mask-editor/backups/`.
- Browser/UI preview screenshots such as `*preview*.png`.
- Local logs, caches, temporary files and `.env*`.

## Before first commit
1. Run:
   ```bash
   python3 scripts/check_public_release.py
   ```
2. Review every file that would be public.
3. Confirm no personal images, generated outputs, credentials, API keys, absolute user paths or local machine identifiers remain.
4. Initialize the public repository only after the check passes.

The local `results/` directory is intentionally preserved on the machine; it is excluded from Git rather than deleted.
