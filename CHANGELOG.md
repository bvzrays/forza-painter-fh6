# Changelog

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
