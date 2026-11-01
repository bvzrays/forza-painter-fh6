from __future__ import annotations

from app_paths import ROOT, SOURCE_DIR


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIR = SOURCE_DIR
PROBE_DIR = ROOT / "webui-data" / "probes"
SESSION_PATH = PROBE_DIR / "current-fh6-session.json"
FULL_SHAPE_ROOT = ROOT / "runtime" / "full-shape-io"
# Generate-page outputs: image/<ext>/ archives every source image that was
# sent to the generator; out/<image stem>/<ext>/ collects the JSON files of
# one image and never holds images.
GENERATED_IMAGE_DIR = ROOT / "image"
GENERATED_OUTPUT_DIR = ROOT / "out"


# ---------------------------------------------------------------------------
# Limits & thresholds
# ---------------------------------------------------------------------------
MEMORY_SNAPSHOT_LIMIT_MB = 2048
PREVIEW_MAX = 520
DETAILED_LOG_OUTPUT_LIMIT = 50000
DETAILED_LOG_MEMORY_LIMIT = 120000
FH6_AUTO_LOCATE_MAX_SECONDS = 300
FH6_AUTO_LOCATE_TIMEOUT_SECONDS = 360
UPDATE_CHECK_TIMEOUT_SECONDS = 8


# ---------------------------------------------------------------------------
# Update URLs
# ---------------------------------------------------------------------------
UPDATE_VERSION_URL = (
    "https://raw.githubusercontent.com/bvzrays/forza-painter-fh6/main/src/version.py"
)
UPDATE_CHANGELOG_URL = (
    "https://raw.githubusercontent.com/bvzrays/forza-painter-fh6/main/CHANGELOG.md"
)
UPDATE_RELEASE_URL = "https://github.com/bvzrays/forza-painter-fh6/releases/latest"
MARKET_URL = "https://painter6.com"


# ---------------------------------------------------------------------------
# Theme colours (dark)
# ---------------------------------------------------------------------------
class Theme:
    BG = "#0d1117"
    PANEL = "#151b23"
    PANEL_ALT = "#1c2430"
    INPUT = "#0b1017"
    TEXT = "#e6edf3"
    MUTED = "#9aa7b4"
    ACCENT = "#58a6ff"
    ACCENT_DARK = "#1f6feb"
    WARN = "#f2cc60"
    BORDER = "#303d4f"
    BUTTON = "#263241"
    BUTTON_ACTIVE = "#334456"
