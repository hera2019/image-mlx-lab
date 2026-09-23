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
- Never expose the local web UI or model server beyond localhost without explicit permission.
- Never upload user images, generated images, intermediate model outputs, logs, or performance data to GitHub.
- Never assume `results/` is disposable. It is private local data and must be preserved unless the user explicitly asks to delete it.
- Do not force-push or rewrite Git history unless explicitly requested.

## Runtime and ports

- Web UI: `http://127.0.0.1:18080/web/mask-editor/`
- Model server: `127.0.0.1:11234`
- Model weights live outside the repository under `~/Documents/AI-Models/image/`.
- Local runtime source/build lives in ignored `worktrees/mlx-serve/`.
- `scripts/setup_model.py --runtime-only` pins the expected mlx-serve commit and applies `patches/qwen-image-2.1-true-edit-mlx.patch`.
- The patch must continue to apply cleanly to the pinned runtime commit.

## Private local data

The entire `results/` tree is ignored by Git.

Important subdirectories:
- `results/web/`: final visible generated/edited images.
- `results/library/`: locally loaded images.
- `results/intermediate/`: raw model intermediate outputs; not final Mask results.
- `results/performance/`: generation timing and memory/swap logs.
- Other `results/*` folders are local experiments and must not be published.

Before any public release, run `python3 scripts/check_public_release.py` and review `PUBLIC_RELEASE.md`.

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
- When switching to another image with unsaved changes, never silently discard the draft. Offer: save as new + switch, overwrite current + switch (when allowed), discard + switch, or cancel.
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
- Status/progress messages belong in the fixed bottom status drawer and should remain visible while the page scrolls.
- The bottom status drawer is collapsed by default. Long-running work (generation / AI edit), important completion notices, validation problems, and errors may open it automatically. Routine informational messages should be logged without forcing it open.

## Development workflow

- Keep changes small and test the affected path before moving on.
- For web changes, at minimum run syntax checks for `app.js` and `server.py`.
- For model-path changes, also check `/api/status` and a minimal generation/edit smoke test when practical.
- Do not run expensive model tests merely to exercise unrelated UI changes.
- When a model test is run, preserve timing/performance logging.
- Keep the Chinese UI as the current source UI. English UI/documentation is planned later, after the Chinese interaction model stabilizes.

## Documentation rule

`docs/PROJECT_GUIDE.md` is the single source of truth for project-wide operating rules.

`AGENTS.md` and `CLAUDE.md` are entry-point files only. They must stay short and point here instead of duplicating the rules.

If architecture, safety boundaries, result directories, runtime assumptions, or major UX invariants change, update this document in the same change.
