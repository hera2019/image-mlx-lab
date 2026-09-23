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
- Editing is non-destructive: source images remain unchanged unless the user explicitly deletes them.
- Saving an edit always creates a new image object/file.
- The right image library may show loaded, generated, edited, and intermediate images; intermediate images must be clearly labeled and not confused with final outputs.
- If an image selection exists, brightness/contrast/saturation/blur/sharpen operate on the selection; otherwise they operate on the whole image.
- Copy/Cut/Paste must work across images. Paste remains a temporary layer until confirmed and supports position, proportional/non-proportional size, and opacity.
- Mask is both a normal selection mechanism and the control region for AI local edit.
- AI local edit must freeze the source image and Mask at request start.
- AI local edit should normally send only a padded crop around the frozen Mask bounding box to Qwen, not a downscaled full frame.
- The crop must preserve enough surrounding context, use a safe MLX/Qwen processing size, then be placed back at the exact original coordinates. Small local crops currently aim for about a 640 px long side while respecting the visual-token and 1152 px safety limits.
- If the padded crop covers most of the image (currently >=72%), automatically fall back to full-frame processing.
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
