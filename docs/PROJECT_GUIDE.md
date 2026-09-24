# Image MLX Lab — Project Guide

This is the canonical project instruction document for humans and coding agents.

## Project identity

- Project name: **Image MLX Lab**
- Local root: `~/Documents/image-mlx-lab`
- GitHub: `hera2019/image-mlx-lab` (currently private)
- Goal: a local Apple Silicon / MLX image generation and editing research workbench.
- Current model backend: Qwen-Image-2.1 MLX.
- The project name is intentionally model-agnostic so other MLX image models can be added later.

## Core safety rules

- Work only inside this repository unless the user explicitly authorizes another path.
- External model weights are read from `~/Documents/AI-Models/`; do not delete, move, replace, or download large model files without explicit permission.
- Never expose the local web UI or model server beyond localhost without explicit permission. LAN access is a possible future feature; it must be an explicit opt-in, not a default.
- The web server (`web/mask-editor/server.py`) is a security boundary even on localhost. Keep its guards:
  - serve only the UI files in `web/mask-editor/` (no backups, logs, `__pycache__`, dotfiles) and library images directly inside `results/{web,library,intermediate}/`; never the repo root, `.git`, other `results/` data or settings;
  - reject requests whose `Host` is not `127.0.0.1:18080` / `localhost:18080` (DNS-rebinding guard);
  - accept POSTs only as `application/json` from the Workbench origin (`Origin` / `Sec-Fetch-Site` checks) so other websites cannot delete, overwrite or generate through it;
  - do not add CORS headers.
- Never upload user images, generated images, intermediate model outputs, logs, or performance data to GitHub.
- Never assume `results/` is disposable. It is private local data and must be preserved unless the user explicitly asks to delete it.
- Do not force-push or rewrite Git history unless explicitly requested.

## Runtime and ports

- Web UI: `http://127.0.0.1:18080/web/mask-editor/`
- Model server: `127.0.0.1:11234`
- Model weights live outside the repository under `~/Documents/AI-Models/image/`.
- Local runtime source/build lives in ignored `worktrees/mlx-serve/`.
- `scripts/setup_model.py --runtime-only` pins the expected mlx-serve commit and applies `patches/qwen-image-2.1-true-edit-mlx.patch`.
- True Edit and AI local edit need `text_encoder/qwen21_visual.safetensors` inside the model folder (the Qwen3-VL visual tower, ~1.1 GB, cut from the official BF16 shard by `scripts/fetch_edit_vision.py`). It is optional per variant: `setup_model.py` asks (or takes `--edit-vision` / `--skip-edit-vision`; non-interactive default is skip), and the server refuses those two modes with a clear message when the running variant lacks it. Never download it without the user's choice.
- The web server owns the model process. On start it launches `scripts/start_server.sh` with the saved variant unless an `mlx-serve` is already listening (`server.py --no-model` skips this for UI-only work).
- `/api/status` reports `server_version` (sha256 prefix of the running `server.py`). `Start-Image-MLX-Lab.command` compares it with the file on disk and restarts an outdated web server (the model keeps running); if a job is running it only prints a notice. After changing `server.py`, restart the web server or double-click Start.
- Model variants: 4-bit and 8-bit. The default is recommended from installed variants and total RAM (8-bit only at >=48 GB). The user can choose the variant and "skip memory preflight" in the UI; the choice is saved in `results/settings.json`. Switching stops the running `mlx-serve` and starts the other variant; it is refused (server 409, UI "apply" disabled) while a model job runs **or while a model is still switching / loading**.
- Model log: `~/.mlx-serve/logs/image-mlx-lab-model.log`. When a start fails, the UI shows the relevant log lines and explains memory-preflight refusals.
- Only one model job (generation / variation / True Edit / AI local edit / model switch) runs at a time; the server returns 409 for a second one and 503 while the model is not ready. The UI reads `busy` from `/api/status`, so a job started in another tab or window also disables the run buttons.
- The patch must continue to apply cleanly to the pinned runtime commit.

## Private local data

The entire `results/` tree is ignored by Git.

Important subdirectories:
- `results/web/`: final visible generated/edited images.
- `results/library/`: locally loaded images.
- `results/intermediate/`: raw model intermediate outputs; not final Mask results.
- `results/performance/`: generation timing and memory/swap logs.
- `results/settings.json`: the model variant / memory-preflight choice made in the UI.
- Other `results/*` folders are local experiments and must not be published.

Before any public release, run `python3 scripts/check_public_release.py` and review `PUBLIC_RELEASE.md`.
Public screenshots / demo images go only in `docs/images/` and must be listed in `docs/images/APPROVED.txt`; the release check blocks every other image.
Licensing: `LICENSE` is plain MIT (Houjun Co., Ltd.) for the source code; model-license notes live in `NOTICE` and the README.
Review feedback and how each point was handled is recorded in `docs/REVIEW_LOG.md`.

## UI and editing invariants

- Top-level modes: text-to-image, variation, True Edit, image editor.
- The four top-level mode buttons change **only the left tool sidebar**.
- The center main-image viewport and the right image library remain present in every mode.
- Clicking an image in the right library changes the center current/main image and must not switch the top-level mode.
- When entering Variation or True Edit, the center current image automatically becomes that mode's main/source image.
- After a generation finishes, the new result becomes the center current image and is added to the right library; earlier/original generations remain available in the library for comparison.
- Editing is non-destructive by default.
- Manual editor saves offer two explicit choices: **Save as new image** (default/non-destructive) or **Overwrite current image**. Overwrite requires explicit confirmation and is allowed only for files managed inside the Workbench results library.
- The editor tracks a saved history index. Undo/Redo must restore exact image + Mask snapshots symmetrically, and the UI must indicate whether the current draft has unsaved pixel changes.
- When switching to another image with unsaved changes, never silently discard the draft. Offer: save as new + switch, overwrite current + switch (when allowed), discard + switch, or cancel. This applies to every switch, including a finished generation opening its result; if the user cancels, the result stays in the library. Esc / closing the dialog means cancel.
- Closing or reloading the page with an unsaved draft, a pending adjustment preview, or an unconfirmed Paste must trigger the browser's leave-page confirmation.
- With no image loaded the center shows the empty-state hint and save / overwrite / download / undo controls are disabled.
- The right image library may show loaded, generated, edited, and intermediate images; intermediate images must be clearly labeled and not confused with final outputs.
- If an image selection exists, brightness/contrast/saturation/blur/sharpen operate on the selection; otherwise they operate on the whole image.
- Viewer zoom is center-anchored: changing zoom must preserve the same image coordinate at the center of the viewport (within normal pixel rounding).
- Copy/Cut/Paste must work across images. Paste remains a temporary layer until confirmed and supports position, proportional/non-proportional size, and opacity. After Paste is confirmed, the selection must follow the pasted content's transformed position/size so the user can immediately continue editing that region.
- Mask is both a normal selection mechanism and the control region for AI local edit.
- AI local edit must freeze the source image and Mask at request start.
- AI local edit offers four context modes: Auto, Local-first, Local + full-image reference, and Full-frame.
- Local-first sends only a padded high-resolution crop around the frozen Mask bounding box plus the local Mask.
- Local + full-image reference sends the same local crop + local Mask and adds a low-resolution whole-image reference for subject identity, pose, background, texture continuity, and occlusion relationships.
- Because a whole-image reference can sometimes make Qwen return a full-frame composition instead of the requested local framing, the browser must classify the returned framing. If the result is full-frame-like, map the original crop coordinates into that result and extract only the corresponding region before compositing; never shrink an entire returned frame into the local Mask region.
- Auto prefers Local-first for compact local edits; prompts involving removal, occlusion recovery, restoration, inpainting, reconstruction, or similar structural completion should resolve to Local + full-image reference. Geometrically broad/dispersed selections should also favor global reference.
- Full-frame sends the complete frozen source + full Mask.
- The crop must preserve enough surrounding context, use a safe MLX/Qwen processing size, then be placed back at the exact original coordinates. Small local crops currently aim for about a 640 px long side while respecting the visual-token and 1152 px safety limits.
- If Auto sees a padded crop covering most of the image (currently >=72%), automatically fall back to Full-frame.
- Raw Qwen local-edit output is not a final image. Apply the frozen full-size Mask deterministically after the edited crop is placed back into the frozen source.
- Outside the original frozen Mask, final pixels must remain unchanged. Reject the result if the safety check detects outside-Mask changes.
- After successful AI local edit, save a new image, switch the editor to that new file, clear the old Mask, and start a fresh undo history.
- Record model generation time and relevant performance data.

## Browser behavior

After changing web UI code:
- Do not open a new browser tab/window when an existing Workbench page is already open.
- Prefer refreshing the existing page.
- If automatic refresh is not practical, tell the user to refresh manually.
- Every status message is logged in the "状态 / 提示" panel at the bottom of the right sidebar (newest first, last 80 kept).
- `notify(message, scope, level)` levels: `quiet` (log only, for routine steps), `progress` (toast that stays until the next toast; long-running work), `important` (toast, auto-hides; completions), `warn` (toast, auto-hides; validation problems such as "请先选择…"), `error` (toast that stays until closed; failures). Toasts sit in the bottom-right corner as a semi-transparent overlay.
- When a collapsible tool section in the image-editor left sidebar is opened, automatically scroll that sidebar enough to reveal the newly expanded content instead of leaving the expansion below the visible area.
- The top-right model badge shows the running variant and state (在线 / 加载中 / 切换中 / 启动失败); clicking it opens the model settings dialog. Run buttons are disabled with a tooltip while the model is not ready or another job runs.
- Static files are served with `Cache-Control: no-cache` so a refresh always pairs the current `index.html` with the current `app.js` / `app.css`. Still bump the `?v=` query when changing them.
- Layout breakpoints (`app.css`): desktop >1100px fits the viewport with independently scrolling columns; 851–1100px keeps three narrower columns with a scrolling page; <=850px is a single column. The right image library must stay visible at every width.

## Development workflow

- Keep changes small and test the affected path before moving on.
- For web changes, at minimum run syntax checks for `app.js` and `server.py`.
- `app.css` is one consolidated stylesheet organized by component. Edit the existing rule instead of appending a new override block at the end.
- For model-path changes, also check `/api/status` and a minimal generation/edit smoke test when practical.
- Do not run expensive model tests merely to exercise unrelated UI changes.
- When a model test is run, preserve timing/performance logging.
- Keep the Chinese UI as the current source UI. English UI/documentation is planned later, after the Chinese interaction model stabilizes.
- When translating, change only user-facing UI text. The Chinese strings in `buildLocalAiPrompt` (app.js), the True Edit reference-role prefixes (`<imageN>仅作为…参考。`) and the transparent-background suffix are **model prompts**, tuned for the model; do not translate or reword them as part of UI localization. `roleLabel()` currently feeds both the reference-role dropdown and that prompt prefix: split it into a UI label and a prompt label before translating the dropdown.

## Documentation rule

`docs/PROJECT_GUIDE.md` is the single source of truth for project-wide operating rules.

`AGENTS.md` and `CLAUDE.md` are entry-point files only. They must stay short and point here instead of duplicating the rules.

If architecture, safety boundaries, result directories, runtime assumptions, or major UX invariants change, update this document in the same change.


## Traditional selection and repair tools

- Selection tools include rectangle, ellipse, freehand lasso add/subtract, brush add/erase, magic-wand add/subtract, invert, clear, and explicit Expand / Contract by pixel radius.
- Expand / Contract is especially useful around AI removal masks: Expand can consume a few residual edge pixels; Contract can protect subject boundaries.
- Deterministic repair tools include Clone Stamp and Spot Healing.
- Clone Stamp samples with Option/Alt-click and paints from a frozen stroke-start source so the sample does not recursively contaminate itself during one stroke.
- Spot Healing is intended for small dust, spots, and scratches. It fills only the painted repair mask from surrounding pixels; complex texture or large missing regions should use Clone Stamp or AI local edit instead.
- Clone/Healing pixel edits must participate in normal Undo/Redo and unsaved-draft protection.
