# Public Release Checklist — Image MLX Lab

Before creating or pushing the public GitHub repository:

## Never publish
- `results/` — user-loaded images, generated images, masks, edited outputs, performance logs, `settings.json`.
- `.venv/`, `worktrees/`, local runtime builds and toolchains.
- Model weights such as `*.safetensors`, `*.gguf`, `*.onnx`, `*.pth`, `*.pt`, `*.bin`.
- `web/mask-editor/backups/`.
- Browser/UI preview screenshots such as `*preview*.png`.
- Local logs, caches, temporary files and `.env*`.

## Public images (screenshots, demo pictures)
- Put them only in `docs/images/` and list each file name in `docs/images/APPROVED.txt` after checking it by eye.
- Never copy anything from `results/`; generate dedicated demo images from neutral prompts instead.
- No personal photos, user names, local paths, other apps' windows or notifications visible; strip EXIF / GPS metadata.
- Any image outside `docs/images/`, or not listed in `APPROVED.txt`, fails the release check.
- Treat approved image file names as immutable. If a screenshot/demo image changes, save it under a new file name and approve that new name; do not replace an already committed public image in place.

## Before any public release
1. Run:
   ```bash
   python3 scripts/check_public_release.py
   ```
   It checks the files that would be published **and all of Git history** (every path and every line ever committed): making the repository public publishes all of its commits.
2. Review every file that would be public.
3. Confirm no personal images, generated outputs, credentials, API keys, absolute user paths or local machine identifiers remain.
4. Confirm `LICENSE` is the unmodified MIT text (Copyright Houjun Co., Ltd.) so GitHub / SPDX detect it, and that `NOTICE` and the README still state that the model weights are not included and fall under the Qwen Research License (non-commercial). Model-license notes belong in `NOTICE` / README, never appended to `LICENSE`.
5. Initialize the public repository only after the check passes.

The local `results/` directory is intentionally preserved on the machine; it is excluded from Git rather than deleted.
