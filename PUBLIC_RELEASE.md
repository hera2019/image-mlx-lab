# Public Release Checklist — Image MLX Lab

Before creating or pushing the public GitHub repository:

## Never publish
- `results/` — user-loaded images, generated images, masks, edited outputs, performance logs, `settings.json`.
- `.venv/`, `worktrees/`, local runtime builds and toolchains.
- Model weights such as `*.safetensors`, `*.gguf`, `*.onnx`, `*.pth`, `*.pt`, `*.bin`.
- `web/mask-editor/backups/`.
- Browser/UI preview screenshots such as `*preview*.png`.
- Local logs, caches, temporary files and `.env*`.

## Before any public release
1. Run:
   ```bash
   python3 scripts/check_public_release.py
   ```
   It checks the files that would be published **and every path in Git history**: making the repository public publishes all of its commits.
2. Review every file that would be public.
3. Confirm no personal images, generated outputs, credentials, API keys, absolute user paths or local machine identifiers remain.
4. Confirm the repository has a `LICENSE` for the project code, and that the README still states the model weights are not included and fall under the Qwen Research License (non-commercial).
5. Initialize the public repository only after the check passes.

The local `results/` directory is intentionally preserved on the machine; it is excluded from Git rather than deleted.
