# Changelog

## v1.9.1 / 2026-06-17

- **Region Paint checkpoints** — Every pass (First Pass and each Paint Selected Region) now saves an independent checkpoint JSON, preview, and heatmap under `checkpoints/` with unique `passN_attemptM` naming. Users can freely switch between any past checkpoint via the Pass History list without losing data.
  - Re-running the same pass after a rollback creates a new attempt instead of overwriting the previous result.
  - Select any checkpoint in the Pass History list and click "Restore Checkpoint" to instantly switch the active state, preview, and heatmap.
  - Switching checkpoints is non-destructive — all historical snapshots are preserved on disk.
  - Step 4 actions, Pass History, and result buttons are now in a separate scrollable area below Steps 1–3 for better small-screen usability.

## v1.9.0 / 2026-06-14

- **Text Vinyl** — New Text tab for generating FH6 typecode JSON from typed Unicode text. Supports Latin, Japanese, Korean, and Chinese (Simplified/Traditional) script panels with localized UI (English, Spanish, Portuguese, Simplified/Traditional Chinese, Korean).
  - **Text input**: Type or paste text in any supported script; CJK text is auto-detected for optimal shape-mode selection.
  - **Font browser**: Upload `.ttf`/`.otf`/`.ttc` files directly, or browse installed CJK fonts discovered on the system. Fonts are sorted alphabetically.
  - **Exact color picker**: Integrated DxBang's color converter with hex-value (`#RRGGBB`) entry for precise text color selection.
  - **Import flow**: Text-generated JSON is wired into the existing Import page flow with dismissible guidance about circle-template compatibility and save/reload behavior.
  - **Pixel art geometry** (`pixel_art_geometry`): Image tracer that converts pixel art into scaled typecode geometry for import.
  - **Shared color palette** (`saved_color_swatches`): Cross-tab color swatch system for reusing favorite colors across Image, Text, and Region Paint workflows.
  - **Workspace management** (`asset_workspace`): Structured runtime directories with safe cache cleanup, manifest tracking, and copy-on-write file staging.
  - **Security policy** (`security_policy`): Shared numeric limits for geometry operations and template layer budgets.
  - **CLI** (`text/cli.py`): Command-line interface for generating text geometry JSON from typed CJK text or text images.
  - **Tests**: 13 new test files covering text geometry, fonts, stroke tracing, character libraries, layer masks, layout, and import templates.

## v1.8.5 / 2026-06-13

- **Region Paint budget guard**: Clicking `Start First Pass` when First-pass layers exceed Total Budget, or clicking `Paint Selected Region` when used layers + Region layers exceed Total Budget, now shows a clear log warning and stops instead of silently overrunning the budget.
- **Multi-direction drag support**: Rectangle and Ellipse selection tools in Region Paint now work when dragging in any direction (e.g. bottom-right to top-left). Previously non-top-left-to-bottom-right drags would fail with a mask generation error.
- **Clear mask improvements**: The `Clear All` button (renamed from "Clear Mask") removes all selection masks. A new `Clear Selected` button deletes only the currently selected mask, logging a hint if nothing is selected.
- **Small-screen accessibility**: Duplicate `Open Result Folder` and `Save Result JSON` buttons added inside the scrollable Step 3 area with a "(for small screens)" hint, so laptop users can still access result actions when the bottom buttons are off-screen.

## v1.8.4 / 2026-06-07

- Region Paint selection shapes (rectangle and ellipse) now support **drag to move**, **corner-handle resize**, and **rotation** via slider, scroll wheel, entry box, or on-canvas rotation handle for precise region refinement.
- Added a new recommended preset that produces great results with relatively low compute power.

## v1.8.3 / 2026-06-06

- Added a **Heatmap** tab to the Region Paint right canvas. After each pass (First Pass / Paint Selected Region) a shape-density heatmap is automatically generated from the geometry JSON and displayed alongside the rendered preview. The two tabs share a cache so switching is instant.
- Significantly improved Region Paint preview image generation speed.

## v1.8.2 / 2026-06-06

- Removed the Feather control from the Region Paint tab's Step 3 selection tools. The feather (Gaussian blur) on selection masks was causing issues with the Paint Selected Region feature. Selection masks are now always hard-edged (0 feather) for reliable region painting.

## v1.8.1 / 2026-06-05

- Added Region Paint — a new iterative painting workflow that generates a base layer pass across the whole image, then lets you select regions (using Rectangle or Ellipse tools) and refine only those areas with additional layers. Includes layer budget management, pass history tracking, live preview on a dedicated right canvas, and result JSON export.
- Fixed the UI log area at the bottom of the window being partially hidden behind the Notebook tabs, ensuring logs are always visible regardless of which tab is active.

## v1.8.0 / 2026-06-01

- Updated the app version to `v1.8.0`; release packages now use `forza-painter-fh6-v1.8.0.exe`.
- Added experimental FH6 full-shape import/export flow: full-shape import lives on the Import page, and game-group export lives on the Export page.
- Import now auto-detects full-shape/type-code JSONs from the normal JSON list and routes them through the full-shape importer.
- Full-shape detection now recognizes exported type-code JSON, Kloudy/Fabric handmade JSON, FH6 full type codes, hex/string shape words, font-shape fields, and common primitive names such as `Circle`, `Square`, `Triangle`, and `Ellipse`.
- Added resource-based preview rendering for FH6 type-code JSON exports and Kloudy/Fabric handmade JSONs, using the bundled FH6 vinyl vertex resources instead of rectangle fallbacks.
- Type-code preview now treats mask layers as transparent cutouts instead of drawing mask shapes as ordinary filled blocks.
- Full-shape failures now show a direct user-facing reminder with the key FH6/editor/template checks.
- Full-shape import success now shows a save/reopen reminder because FH6 can keep showing stale live template resources until the saved vinyl group is reloaded.
- Full-shape probe/import/export reports are kept out of the normal log flow and can be exported manually as a ZIP when debugging is needed.
- Full-shape export reads the current editable FH6 group into JSON using the 16-bit shape word at layer offset `0x7A`.
- Full-shape import writes only stable visual fields (`position`, `scale`, `rotation`, `skew`, `color`, `mask`, and `shape word`) and does not copy volatile resource pointers such as `0xA8`.
- Full-shape import can clear unused template slots and trim the FH6 group count/table end after writing.
- Included the Kloudy's FH6 Painter custom-importer MIT attribution, font-shape registry, and FH6 vinyl resource data used by the type-code importer/previewer.
- Moved image/JSON preview rerendering off the Tk UI thread, debounced resize-triggered preview refreshes, and throttled width-driven Tk layout updates to reduce horizontal window-resize stutter.

## v1.7.0 / 2026-06-01

- Updated the app version to `v1.7.0`; release packages now use `forza-painter-fh6-v1.7.0.exe`.
- Added a prominent Preset Market banner to the Generate, Import, Tools, and Tutorial pages.
- The new market button opens https://painter6.com so users can browse shared images, presets, and JSON packages directly from the app.

## v1.6.8 / 2026-05-28

- Updated the app version to `v1.6.8`; release packages now use `forza-painter-fh6-v1.6.8.exe`.
- Integrated the latest GitHub `main` changes from PR #87, keeping ellipse width/height as floating-point values for more accurate FH6 imports.
- Added an in-app preview note explaining that v1.6.8 favors better in-game results while previews remain approximate.
- Improved JSON preview rendering with supersampling so float-sized ellipses look less jagged or degraded in the preview panel.

## v1.6.7 / 2026-05-27

- Updated the app version to `v1.6.7`; release packages now use `forza-painter-fh6-v1.6.7.exe`.
- Updated the bundled GPU generator to upstream `canary-26052702`.
- Replaced FH6 import scale magic numbers with named `FH6_CIRCLE_BASE_SIZE` and `FH6_RECTANGLE_BASE_SIZE` constants so the in-game circle base size can be adjusted explicitly.
- Improved generation ETA estimation so buffered generator output and early slow phases do not keep the remaining-time display wildly inaccurate.

## v1.6.6 / 2026-05-26

- Updated the app version to `v1.6.6`; release packages now use `forza-painter-fh6-v1.6.6.exe`.
- Added Traditional Chinese UI translations and a wider top-right language selector.
- Fixed `luma_band` preprocessing for RGB images and made preprocessed-image writes atomic.
- Packaged OpenCV and NumPy into the one-file EXE so `luma_band` preprocessing works in release builds.
- Import now requires the FH6 template layer count before starting, preventing confusing auto-locate/import failures caused by an empty layer-count field.
- Refactored core modules with typed exceptions, frozen dataclasses, and shared utility helpers.
- Added pytest coverage for geometry JSON normalization and internal color/shape data classes.

## v1.6.5 / 2026-05-25

- Updated the app version to `v1.6.5`; release packages now use `forza-painter-fh6-v1.6.5.exe`.
- Updated the bundled GPU generator to upstream `v1.2-Canary-20260525`.
- Bundled presets now set `forceOpaqueShapes = false` by default so transparent source regions can remain transparent unless users override the setting.
- Generator launches now use a sanitized environment to avoid external Python, Conda, WebUI, Vulkan, or OpenCL override variables affecting the bundled GPU generator.
- Reduced generation-time filesystem polling so the app checks previews and JSON outputs less aggressively while the GPU generator is running.
- The heaviest bundled preset now uses `previewEvery = 100` instead of `previewEvery = 1`, avoiding excessive preview PNG writes during high-resolution generation.
- Fixed output discovery for preprocessed generation inputs so generated JSON and preview files are tracked from the actual image passed to the GPU generator.

## v1.6.1 / 2026-05-24

- Updated the app version to `v1.6.1`; release packages now use `forza-painter-fh6-v1.6.1.exe`.
- Disabled `luma_band` preprocessing by default in bundled presets.
- Import no longer reuses stale FH6 session data from `webui-data`; it re-locates the current template before writing.
- JSON previews now use one stable renderer path to avoid ellipse preview distortion differences between packaged EXE environments.

## v1.6.0 / 2026-05-24

- Updated the app version to `v1.6.0`; release packages now use `forza-painter-fh6-v1.6.0.exe`.
- Updated the bundled GPU generator to upstream `canary-26052401`.
- Added upstream `errorGridSize` preset support.
- Integrated the upstream transparent-area overhang prevention algorithm adjustment.
- Significantly improved generation quality for the large ellipse at the bottom of transparent images.

## v1.5.4 / 2026-05-23

- Fixed preview scaling for high-resolution source images, generator preview PNG files, and JSON previews.
- Previews now adapt to the current preview panel size while preserving the original image aspect ratio, avoiding stretched or partially visible previews when using large max-resolution settings such as 3000.
- Fixed JSON preview rendering for type 16 rotated ellipses in the packaged EXE by making the Pillow fallback follow the historical OpenCV preview coordinate conversion.

## v1.5.3 / 2026-05-22

- Added user preset import for the one-file EXE; imported `.ini` presets are stored in the external `config/settings/` folder beside the app.
- Added remove buttons for the selected image and selected JSON entries.
- Improved checkpoint handling: existing checkpoint JSON files are detected and reusable checkpoints are added to the Import list after failed or stopped generation.
- Fixed JSON output discovery when source image filenames contain extra dots, such as `image.1png.png`.
- Improved generation progress logs when the GPU generator recycles fully covered layers, so the UI no longer looks like generation restarted from an earlier layer.
- Added a Pillow-based preview fallback and packaged it into the EXE so fresh one-file installs can preview images and JSON without OpenCV.

## v1.5.2 / 2026-05-22

- Added a PyInstaller-based one-file EXE so normal users no longer need to install Python, create `.venv`, or keep helper files beside the app.
- The GUI EXE now re-launches itself in hidden helper mode for import and FH6 memory probing.
- The Tools page and startup log now show where external runtime/cache files are stored.
- Fixed the batch bootstrap variable-expansion bug that could run `-m venv` instead of `python -m venv`.
- Added a repeatable `scripts/make_exe_release.ps1` build script for the one-file EXE package.

## v1.5.1 / 2026-05-22

- Fixed startup dependency installation when a project `.venv` exists but its Python does not have `pip`; the bootstrapper now runs `ensurepip --upgrade` before installing requirements.
- Improved startup-script diagnostics when required release files are missing, with a clear message to fully extract the release ZIP first.

## v1.5.0 / 2026-05-22

- Added a startup update check against the GitHub `main` branch version file.
- When update checking fails, the app shows a small `!` indicator in the top-right corner; clicking it shows the failure reason.
- When a newer version is available, the app displays this changelog section and lets the user open the update page.
- Switched the desktop UI to a dark theme for better contrast during long generation and import sessions.
- Updated the bundled GPU/OpenCL generator to upstream `canary-26052102`.
- Added the upstream work-group evaluation algorithm from PR #4, reducing GPU candidate-evaluation overhead and improving generation throughput on supported OpenCL devices.
- `start_app.bat` now bootstraps the project-local `.venv`: it installs missing dependencies and then launches the app.
- Dependency installation now uses `.venv` instead of installing packages into the global Python environment.

## v1.4.1 / 2026-05-21

- FH6 template auto-location now tries both the v1.3 small/medium-region address-order scan and the v1.4 large-region chunked scan before giving up.
- Added an RTTI vtable fallback locator for difficult FH6 sessions while keeping the existing safe table validation before writing.
- Raised the FH6 auto-location budget to 300 seconds, with a 360-second outer watchdog timeout.
- Added a user-facing wait message before FH6 auto-location starts, warning users to keep the Vinyl Group Editor open and avoid switching menus.

## v1.4.0 / 2026-05-21

- Added detailed log export with a 50000-character output limit.
- Detailed logs include helper/generator raw output, commands, exit codes, process/template state, and current session data.
- Improved FH6 template auto-location by scanning large writable private memory regions in 4 MB chunks.
- Increased the FH6 auto-location scan budget to 120 seconds and the outer watchdog timeout to 160 seconds.

## v1.3.0 / 2026-05-21

- Updated the bundled GPU/OpenCL generator to upstream `canary-26052101`.
- Added the upstream generator device-selection fix, prioritizing NVIDIA GPUs with the most VRAM.
- Generation logs now show the selected OpenCL device.
- Improved FH6 template auto-locate failure handling so stale session cache is not reported as a newly verified template.
