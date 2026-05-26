<p align="center">
  <img src="https://github.com/user-attachments/assets/d4f48f71-d76e-4ffe-9fb1-0b075d79bf05" alt="forza-painter FH6 logo" width="720">
</p>

<h1 align="center">forza-painter FH6</h1>

<p align="center">
  <strong>Image to Forza Horizon 6 Vinyl Group generator and importer.</strong>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">中文</a> ·
  <a href="README.ko-KR.md">한국어</a>
</p>

<p align="center">
  <code>v1.6.6</code> · <code>Windows</code> · <code>Forza Horizon 6</code> · <code>GPU/OpenCL</code> · <code>One-file EXE</code>
</p>

Convert PNG/JPG/BMP images into Forza Horizon 6 Vinyl Group layers. The app handles generation, preview, and import in one desktop window; normal users do not need Python, `.venv`, batch files, or manual memory addresses.

> **Download the EXE:** get `forza-painter-fh6-v1.6.6.exe` from [Releases](https://github.com/bvzrays/forza-painter-fh6/releases) and run it directly.

> **If the result looks blurry:** raise `Random samples` first. Values above **200000** usually make a major quality difference; higher values are clearer but take much longer to generate.

> **Import can take time:** v1.4.1+ tries multiple FH6 template locators and can spend up to 5 minutes finding the safe layer table. Keep FH6 in Vinyl Group Editor, do not switch menus, and export a detailed log if it still fails.

| What it does | Details |
| --- | --- |
| Generate JSON | Convert images into geometry JSON with the bundled GPU/OpenCL generator. |
| Preview output | Show source and generated geometry previews inside the app. |
| Import to FH6 | Import JSON into the currently open FH6 Vinyl Group Editor. |
| Safe FH6 workflow | Auto-locate and verify the editable layer table before writing. |
| Update check | Check for new versions on startup and show changelog notes when available. |

## Quick Start

1. Download `forza-painter-fh6-v1.6.6.exe` from [Releases](https://github.com/bvzrays/forza-painter-fh6/releases).
2. Put the EXE in a normal writable folder, for example `Desktop\forza-painter-fh6`.
3. Double-click the EXE. For FH6 import, run it as administrator if Windows blocks process access.
4. In FH6, open `Create Vinyl Group` / `Vinyl Group Editor`, load a sphere template, then `Ungroup` it.
5. In the app, generate JSON, open the `Import` page, enter the exact template layer count, then import.

Do not download GitHub's automatic `Source code` ZIP unless you are developing the project. Normal users only need the `.exe`.

## Preview

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/app-import-preview.png" alt="App import page"><br>
      <strong>App import page</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-template-ready.png" alt="FH6 template ready"><br>
      <strong>Template ready in FH6</strong>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-import-result.png" alt="FH6 import result"><br>
      <strong>Imported result</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-car-applied.png" alt="FH6 car applied result"><br>
      <strong>Applied to car</strong>
    </td>
  </tr>
</table>

## Generate JSON

1. Open the `Generate JSON` page.
2. Click `Add images` and choose PNG/JPG/BMP images.
3. Select a quality preset.
4. Optional: enable `Use custom settings` to change output layers, resolution, random samples, and mutated samples.
5. Click the fixed bottom `Start generating` button.
6. Wait for the preview and logs to update.

Generated files are saved beside the source image, for example `image.500.json`, `image.1000.json`, and `image.3000.json`.

One image can generate multiple checkpoint JSON files. Prefer the highest-layer JSON that matches your template; for example, use `image.3000.json` or the final `image.json` with a 3000-layer template. Importing a 500-layer JSON into a 3000-layer template will look blurry.

| Preset | Output layers | Random samples | Use case |
| --- | ---: | ---: | --- |
| extremely fast | 500 | 30000 | Quick composition checks |
| fast | 1000 | 60000 | Quick usable drafts |
| balanced | 1800 | 120000 | Recommended default |
| slow | 2500 | 220000 | Final quality; starts using the 200k+ quality range |
| super slow | 3000 | 350000 | Best clarity, very slow |

## Import JSON

1. Start FH6 and keep `Vinyl Group Editor` open.
2. Load or create a template made from many simple sphere layers.
3. `Ungroup` the template and remember the exact in-game layer count.
4. In the app, open `Import`, click `Refresh`, and select `forzahorizon6.exe`.
5. Enter the exact template layer count.
6. Add the generated `.json`, or click `Use generated JSON`.
7. Leave advanced address fields empty and click `Import JSON`.

FH needs 4 extra boundary layers to save the cover and apply bounds correctly. Example: a 1000-layer JSON should use at least a 1004-layer template; a 3000-layer template can import about 2996 drawable shapes.

## Important Rules

- The FH6 template must be ungrouped before import.
- The layer count in the app must exactly match the game.
- Do not switch game menus while importing.
- After restarting FH6, reloading the template, or changing layer count, import again with the new correct count.
- If JSON has fewer layers than the template, unused template layers are hidden.
- If JSON has more layers than the template, extra shapes are trimmed.
- Transparent PNG backgrounds are not imported as visible backgrounds.

## Runtime Files

The one-file EXE extracts its internal files temporarily and stores normal runtime data outside the EXE. The app shows the exact paths in the startup log and on the `Tools` page.

Expected external folders beside the EXE:

- `runtime/`: logs, generated session data, and temporary app files.
- `webui-data/`: local browser/UI cache.

These folders can be deleted when the app is closed if you want to reset local runtime data.

## Troubleshooting

- **EXE will not import into FH6:** close the app and run the EXE as administrator.
- **GPU/OpenCL error:** update NVIDIA/AMD/Intel graphics drivers. The bundled generator uses OpenCL.
- **Template cannot be located:** confirm you are in Vinyl Group Editor, the template is ungrouped, the layer count is exact, and the menu was not changed during scanning.
- **Imported result is blurry:** use a higher-layer JSON or increase `Output layers` / `Random samples`.
- **Need help debugging:** use `Export detailed log` in the app and attach the log to an issue.

## Resources

- Import walkthrough video: https://www.bilibili.com/video/BV1hG5Z6nENZ
- Bundled GPU generator source/reference: https://github.com/zjl88858/forza-painter-geometrize-gpu
- Full changelog: [CHANGELOG.md](CHANGELOG.md)

## Changelog

Only versioned release entries are kept here. See [CHANGELOG.md](CHANGELOG.md) for the app update prompt changelog.

### v1.6.6 / 2026-05-26

- Updated the app version to `v1.6.6`; release packages now use `forza-painter-fh6-v1.6.6.exe`.
- Added Traditional Chinese UI translations and improved the language selector layout.
- Fixed `luma_band` preprocessing for RGB images, made preprocessed-image writes safer, and added tests for geometry/color data handling.
- Packaged OpenCV and NumPy into the one-file EXE so `luma_band` preprocessing works in release builds.
- Import now requires the FH6 template layer count before starting.
- Refactored core modules with typed exceptions and shared utility helpers.

### v1.6.5 / 2026-05-25

- Updated the app version to `v1.6.5`; release packages now use `forza-painter-fh6-v1.6.5.exe`.
- Updated the bundled GPU generator to upstream `v1.2-Canary-20260525`.
- Bundled presets now set `forceOpaqueShapes = false` by default.
- Reduced main-app overhead during generation by using a sanitized generator environment, slower file polling, and less frequent preview writes in the heaviest preset.
- Fixed generated output tracking when preprocessing creates a separate input image.

### v1.6.1 / 2026-05-24

- Updated the app version to `v1.6.1`; release packages now use `forza-painter-fh6-v1.6.1.exe`.
- Disabled `luma_band` preprocessing by default in bundled presets.
- Import no longer reuses stale FH6 session data from `webui-data`; it re-locates the current template before writing.
- JSON previews now use one stable renderer path to avoid ellipse preview distortion differences between packaged EXE environments.

### v1.6.0 / 2026-05-24

- Updated the app version to `v1.6.0`; release packages now use `forza-painter-fh6-v1.6.0.exe`.
- Updated the bundled GPU generator to upstream `canary-26052401`.
- Added upstream `errorGridSize` preset support.
- Integrated the upstream transparent-area overhang prevention algorithm adjustment.
- Significantly improved generation quality for the large ellipse at the bottom of transparent images.

### v1.5.4 / 2026-05-23

- Fixed preview scaling for high-resolution source images, generator preview PNGs, and JSON previews so the full image fits the current preview panel without stretching.
- Fixed type 16 rotated ellipse rendering in JSON previews so Import page previews no longer flatten or rotate ellipse strokes incorrectly.

### v1.5.3 / 2026-05-22

- Added EXE-friendly custom preset import, image/JSON list removal, checkpoint reuse, safer output naming, and Pillow preview fallback.

### v1.5.2 / 2026-05-22

- Added a true one-file EXE so normal users no longer need Python, `.venv`, or helper files.
- The GUI EXE can relaunch itself in hidden helper mode for import and FH6 memory probing.
- The Tools page and startup log now show external runtime/cache locations.

### v1.5.1 / 2026-05-22

- Fixed startup dependency installation when a project `.venv` exists but its Python does not have `pip`.
- Improved startup-script diagnostics for incomplete source-package extraction.

### v1.5.0 / 2026-05-22

- Updated the bundled GPU/OpenCL generator to upstream `canary-26052102`.
- Added the upstream work-group evaluation algorithm from PR #4 for faster GPU candidate evaluation.
- Added startup update checking, root `CHANGELOG.md`, and the dark desktop UI.

### v1.4.1 / 2026-05-21

- FH6 template auto-location now tries both v1.3 and v1.4 scan strategies before giving up.
- Added an RTTI vtable fallback locator and increased the auto-location wait budget.

### v1.4.0 / 2026-05-21

- Added detailed log export capped at 50000 characters.
- Improved FH6 template auto-location for large writable memory regions.

### v1.3.0 / 2026-05-21

- Updated the bundled GPU/OpenCL generator to upstream `canary-26052101`.
- Added the upstream GPU device-selection fix and selected-device logging.

### v1.2.0 / 2026-05-20

- Updated the bundled GPU/OpenCL generator to upstream `canary-26052001`.
- Added `forceOpaqueShapes = true` to bundled and custom generation settings.

### v1.1.1 / 2026-05-20

- Added centralized version management for the app window, CLI, and release package names.
- Reorganized the repository layout and release packaging.
