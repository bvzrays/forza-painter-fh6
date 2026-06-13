from __future__ import annotations

import argparse
import io
import json
import math
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, BOTTOM, END, LEFT, RIGHT, X, Button, Canvas, Checkbutton, Entry, Frame, IntVar, Label, Listbox, PhotoImage, Spinbox, StringVar, Text, Tk, Toplevel, filedialog, messagebox, ttk

import psutil

from app_paths import ROOT

# Allow importing from project-root packages (e.g. scripts/)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fh6_vinyl_resources import load_vinyl_polygons
from game_profiles import PROFILES
from geometry_json import RECTANGLE, ROTATED_ELLIPSE, load_normalized_geometry
from generator_backend import GENERATOR_EXE, GENERATOR_JSON_SCAN_SECONDS, GENERATOR_POLL_SLEEP_SECONDS, GENERATOR_PREVIEW_SCAN_SECONDS, USER_SETTINGS_DIR, best_geometry_jsons, build_generator_command, build_generator_env, generated_jsons, generated_preview_files, generator_preview_path, load_settings, preprocess_input_image, write_custom_settings, write_user_settings_preset
from region_painter.state_manager import StateManager
from region_painter.workflow import (
    finalize_first_pass,
    finalize_region_pass,
    get_status as region_get_status,
    prepare_first_pass,
    prepare_region_pass,
)
from version import APP_DISPLAY_NAME, __version__, app_title


from app_config import (
    APP_DIR,
    PROBE_DIR,
    SESSION_PATH,
    FULL_SHAPE_ROOT,
    MEMORY_SNAPSHOT_LIMIT_MB,
    PREVIEW_MAX,
    DETAILED_LOG_OUTPUT_LIMIT,
    DETAILED_LOG_MEMORY_LIMIT,
    FH6_AUTO_LOCATE_MAX_SECONDS,
    FH6_AUTO_LOCATE_TIMEOUT_SECONDS,
    UPDATE_VERSION_URL,
    UPDATE_CHANGELOG_URL,
    UPDATE_RELEASE_URL,
    MARKET_URL,
    UPDATE_CHECK_TIMEOUT_SECONDS,
    Theme,
)

from utils import load_cv2, load_pillow

from i18n import tr

LANGUAGES = { 
    "English": "en",
    "Português (Brasil)": "pt-br",
    "中文": "zh",
    "中文 (繁體)": "zh-tw",
    "한국어": "ko",
    "Español": "es",
}

ETA_MAX_PROGRESS_SAMPLES = 400
ETA_WINDOW_SECONDS = 45.0
ETA_MAX_HISTORY_SECONDS = 180.0
ETA_MIN_WINDOW_SECONDS = 4.0
ETA_MIN_WINDOW_LAYERS = 25
PREVIEW_JSON_SUPERSAMPLE = 2
PREVIEW_RESIZE_DEBOUNCE_MS = 500
PREVIEW_RENDER_START_MS = 1
PREVIEW_SIZE_BUCKET = 32
PREVIEW_CACHE_LIMIT = 24
LAYOUT_RESIZE_DEBOUNCE_MS = 180
LAYOUT_SIZE_BUCKET = 64
FH6_CIRCLE_BASE_SIZE = 63.0
FH6_RECTANGLE_BASE_SIZE = 127.0
FH6_TYPE_CODE_BASE = 0x100000
FH6_PRIMITIVE_NAME_WORDS = {
    "square": 0x0065,
    "rectangle": 0x0065,
    "rect": 0x0065,
    "circle": 0x0066,
    "sphere": 0x0066,
    "triangle": 0x0067,
    "circle border": 0x0070,
    "circle outline": 0x0070,
    "ellipse": 0x0088,
    "oval": 0x0088,
}
FH6_TYPECODE_MARKER_KEYS = (
    "type_word",
    "typeWord",
    "shape_word",
    "shapeWord",
    "font_shape",
    "fontShape",
    "shape_name",
    "shapeName",
    "font",
    "font_index",
    "fontIndex",
    "forza_font",
    "forzaFont",
    "glyph",
    "char",
    "character",
    "text",
    "font_block",
    "fontBlock",
)


# Removed: TEXT dictionary (now in i18n.py)


def ensure_dirs():
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    FULL_SHAPE_ROOT.mkdir(parents=True, exist_ok=True)




def version_key(value):
    parts = []
    for part in re.findall(r"\d+", str(value)):
        parts.append(int(part))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def parse_version_source(source):
    match = re.search(r'__version__\s*=\s*"([^"]+)"', source or "")
    if not match:
        raise ValueError("remote version file did not contain __version__")
    return match.group(1).strip()


def fetch_text_url(url, timeout=UPDATE_CHECK_TIMEOUT_SECONDS):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"{APP_DISPLAY_NAME}/{__version__}",
            "Accept": "text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(256 * 1024)
    return data.decode("utf-8", errors="replace")


def extract_changelog_section(changelog, version):
    text = (changelog or "").strip()
    if not text:
        return ""
    heading = re.compile(rf"^(#{{1,6}})\s+v?{re.escape(str(version))}\b.*$", re.I | re.M)
    match = heading.search(text)
    if not match:
        return text[:6000]
    next_heading = re.compile(rf"^{re.escape(match.group(1))}\s+\S+", re.M)
    next_match = next_heading.search(text, match.end())
    end = next_match.start() if next_match else len(text)
    return text[match.start():end].strip()[:6000]


def helper_command(helper_name):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--helper", helper_name]
    return [sys.executable, APP_DIR / f"{helper_name}.py"]


def run_embedded_helper(helper_name, args):
    if helper_name == "fh6_probe":
        import fh6_probe

        previous_argv = sys.argv
        try:
            sys.argv = ["fh6_probe.py", *args]
            return fh6_probe.main()
        finally:
            sys.argv = previous_argv
    if helper_name == "main":
        import main as importer_main

        return importer_main.main(["main.py", *args])
    if helper_name == "fh6_typecode_probe":
        import fh6_typecode_probe

        previous_argv = sys.argv
        try:
            sys.argv = ["fh6_typecode_probe.py", *args]
            return fh6_typecode_probe.main()
        finally:
            sys.argv = previous_argv
    if helper_name == "fh6_typecode_export":
        import fh6_typecode_export

        previous_argv = sys.argv
        try:
            sys.argv = ["fh6_typecode_export.py", *args]
            return fh6_typecode_export.main()
        finally:
            sys.argv = previous_argv
    if helper_name == "fh6_typecode_import":
        import fh6_typecode_import

        previous_argv = sys.argv
        try:
            sys.argv = ["fh6_typecode_import.py", *args]
            return fh6_typecode_import.main()
        finally:
            sys.argv = previous_argv
    if helper_name == "fh6_typecode_trim":
        import fh6_typecode_trim

        previous_argv = sys.argv
        try:
            sys.argv = ["fh6_typecode_trim.py", *args]
            return fh6_typecode_trim.main()
        finally:
            sys.argv = previous_argv
    raise SystemExit(f"Unknown helper: {helper_name}")


def game_processes():
    names = {name.lower(): key for key, profile in PROFILES.items() for name in profile.process_names}
    found = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = proc.info.get("name") or ""
            key = names.get(name.lower())
            if key:
                found.append({
                    "pid": proc.info["pid"],
                    "name": name,
                    "profile": key,
                    "label": f"{name} pid {proc.info['pid']}",
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def parse_hex_or_empty(value):
    value = str(value or "").strip()
    return value or None


def typecode_shape_count(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    shapes = payload.get("shapes")
    if not isinstance(shapes, list):
        raise ValueError("full-shape JSON must contain a shapes list")
    return len(shapes)


def parse_preview_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text, 0)
        except ValueError:
            return None
    return None


def normalize_typecode_name(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()


def shape_has_typecode_marker(shape):
    if not isinstance(shape, dict):
        return False
    if any(key in shape for key in FH6_TYPECODE_MARKER_KEYS):
        return True
    for key in ("type", "name"):
        value = shape.get(key)
        numeric = parse_preview_int(value)
        if numeric is not None and numeric >= FH6_TYPE_CODE_BASE:
            return True
        if normalize_typecode_name(value) in FH6_PRIMITIVE_NAME_WORDS:
            return True
    return False


def is_typecode_payload(payload):
    if not isinstance(payload, dict):
        return False
    fmt = str(payload.get("format") or "")
    if fmt.startswith("fh6_typecode_json"):
        return True
    source = payload.get("source") or {}
    if isinstance(source, dict) and "uint16_at_layer_0x7A" in str(source.get("type_model") or ""):
        return True
    shapes = payload.get("shapes")
    if not isinstance(shapes, list):
        return False
    for shape in shapes:
        if shape_has_typecode_marker(shape):
            return True
    return False


def is_typecode_json(path):
    try:
        return is_typecode_payload(json.loads(Path(path).read_text(encoding="utf-8")))
    except Exception:
        return False


def load_session_location():
    if not SESSION_PATH.exists():
        return None
    try:
        return json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def clear_session_location():
    try:
        SESSION_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def session_pid_is_live(session, game):
    try:
        pid = int(session.get("pid", -1))
        proc = psutil.Process(pid)
        profile = PROFILES.get(game)
        return bool(profile and proc.name().lower() in [name.lower() for name in profile.process_names])
    except (psutil.Error, TypeError, ValueError):
        return False


def session_matches_current_import(session, game, pid, layer_count):
    if not session:
        return False
    if str(session.get("layer_count", "")) != str(layer_count):
        return False
    if not session_pid_is_live(session, game):
        return False
    try:
        session_pid = int(session.get("pid", -1))
        return not pid or int(pid) == session_pid
    except (TypeError, ValueError):
        return False


# load_cv2 and load_pillow are now imported from utils


def preview_size_tuple(max_size=None):
    if max_size is None:
        return PREVIEW_MAX, PREVIEW_MAX
    if isinstance(max_size, (tuple, list)):
        if len(max_size) >= 2:
            width, height = max_size[0], max_size[1]
        elif len(max_size) == 1:
            width = height = max_size[0]
        else:
            width = height = PREVIEW_MAX
    else:
        width = height = max_size
    try:
        width = int(width)
        height = int(height)
    except (TypeError, ValueError):
        width = height = PREVIEW_MAX
    return max(1, width), max(1, height)


def preview_scale(width, height, max_size=None):
    max_w, max_h = preview_size_tuple(max_size)
    if width <= 0 or height <= 0:
        return 1.0
    return min(max_w / width, max_h / height, 1.0)


def resize_keep_aspect(image, max_size=None):
    loaded = load_cv2()
    if not loaded:
        return image
    cv2, _np = loaded
    height, width = image.shape[:2]
    scale = preview_scale(width, height, max_size)
    if scale < 1.0:
        resized_w = max(1, int(round(width * scale)))
        resized_h = max(1, int(round(height * scale)))
        image = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
    return image


def image_to_photo(image, max_size=None):
    loaded = load_cv2()
    if not loaded:
        return None
    cv2, _np = loaded
    image = resize_keep_aspect(image, max_size)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        return None
    return encoded.tobytes()


def pil_to_photo(image, max_size=None):
    loaded = load_pillow()
    if not loaded:
        return None
    Image, _ImageDraw = loaded
    image = image.convert("RGB")
    image.thumbnail(preview_size_tuple(max_size), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_source_image(path, max_size=None):
    loaded = load_cv2()
    if loaded:
        cv2, _np = loaded
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is not None:
            return image_to_photo(image, max_size)
    loaded = load_pillow()
    if not loaded:
        return None
    Image, _ImageDraw = loaded
    try:
        with Image.open(path) as image:
            return pil_to_photo(image, max_size)
    except Exception:
        return None


def _typecode_preview_shapes(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not is_typecode_payload(payload):
        return None
    shapes = payload.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        return None
    out = []
    for shape in shapes:
        if not isinstance(shape, dict):
            continue
        data = list(shape.get("data") or [])
        color = list(shape.get("color") or [])
        if len(data) < 4 or len(color) < 4:
            continue
        try:
            x, y, w, h = [float(v) for v in data[:4]]
            rotation = float(data[4]) if len(data) >= 5 else 0.0
            rgba = [max(0, min(255, int(round(float(v))))) for v in color[:4]]
        except (TypeError, ValueError):
            continue
        type_code = typecode_preview_type_code(shape)
        word = type_code & 0xFFFF if type_code is not None else typecode_preview_word(shape)
        if word is None:
            continue
        if rgba[3] <= 0:
            continue
        skew = float(data[5]) if len(data) >= 6 else 0.0
        resource = load_vinyl_polygons(type_code) if type_code is not None else None
        if resource:
            polygons = [
                [_transform_typecode_point(px, py, x, y, w, h, rotation, skew) for px, py in polygon]
                for polygon in resource["polygons"]
            ]
        else:
            polygons = _fallback_typecode_polygons(x, y, w, h, rotation, skew, word & 0xFFFF)
        try:
            data_mask = bool(int(float(data[6]))) if len(data) >= 7 else False
        except (TypeError, ValueError):
            data_mask = bool(data[6]) if len(data) >= 7 else False
        is_mask = bool(shape.get("mask") or shape.get("is_mask") or shape.get("isMask") or data_mask)
        if polygons:
            out.append({"polygons": polygons, "color": rgba, "word": word & 0xFFFF, "type_code": type_code, "mask": is_mask})
    return out


def typecode_preview_type_code(shape):
    type_code = parse_preview_int(shape.get("type"))
    if type_code is not None and type_code >= FH6_TYPE_CODE_BASE:
        return type_code
    word = None
    for key in ("type_word", "typeWord", "shape_word", "shapeWord"):
        value = parse_preview_int(shape.get(key))
        if value is not None:
            word = value & 0xFFFF
            break
    if word is not None:
        return FH6_TYPE_CODE_BASE + word
    for key in ("shape_name", "shapeName", "name", "type"):
        primitive_word = FH6_PRIMITIVE_NAME_WORDS.get(normalize_typecode_name(shape.get(key)))
        if primitive_word is not None:
            return FH6_TYPE_CODE_BASE + primitive_word
    try:
        from fh6_typecode_import import load_font_registry, shape_type_fields

        resolved_type_code, resolved_word, _font_item = shape_type_fields(shape, load_font_registry())
        if resolved_type_code >= FH6_TYPE_CODE_BASE:
            return int(resolved_type_code)
        return FH6_TYPE_CODE_BASE + (int(resolved_word) & 0xFFFF)
    except Exception:
        return None


def typecode_preview_word(shape):
    type_code = typecode_preview_type_code(shape)
    if type_code is not None:
        return type_code & 0xFFFF
    for key in ("type_word", "typeWord", "shape_word", "shapeWord"):
        value = parse_preview_int(shape.get(key))
        if value is not None:
            return value & 0xFFFF
    type_code = parse_preview_int(shape.get("type"))
    if type_code is not None:
        return type_code & 0xFFFF
    for key in ("shape_name", "shapeName", "name", "type"):
        word = FH6_PRIMITIVE_NAME_WORDS.get(normalize_typecode_name(shape.get(key)))
        if word is not None:
            return word & 0xFFFF
    try:
        from fh6_typecode_import import load_font_registry, shape_type_fields

        _type_code, word, _font_item = shape_type_fields(shape, load_font_registry())
        return int(word) & 0xFFFF
    except Exception:
        return None


def _safe_nonzero_float(value, default=1.0):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric) or numeric == 0.0:
        return default
    return numeric


def _transform_typecode_point(local_x, local_y, shape_x, shape_y, scale_x, scale_y, rotation, skew):
    sx = _safe_nonzero_float(scale_x)
    sy = _safe_nonzero_float(scale_y)
    x = float(local_x) * sx
    y = float(local_y) * sy
    x = x + float(skew) * y
    theta = math.radians(-float(rotation))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    return (
        float(shape_x) + x * cos_t - y * sin_t,
        -float(shape_y) + x * sin_t + y * cos_t,
    )


def _fallback_typecode_polygons(x, y, sx, sy, rotation, skew, word):
    base_size = FH6_CIRCLE_BASE_SIZE if word in (0x66, 0x88) else FH6_RECTANGLE_BASE_SIZE
    if word in (0x66, 0x88):
        points = []
        steps = 48
        for i in range(steps):
            theta = (math.pi * 2.0 * i) / steps
            points.append((math.cos(theta) * base_size, math.sin(theta) * base_size))
        return [[_transform_typecode_point(px, py, x, y, sx, sy, rotation, skew) for px, py in points]]
    half = base_size / 2.0
    points = ((-half, -half), (half, -half), (half, half), (-half, half))
    if word == 0x67:
        points = ((0.0, -half), (half, half), (-half, half))
    return [[_transform_typecode_point(px, py, x, y, sx, sy, rotation, skew) for px, py in points]]


def _rotated_points(cx, cy, width, height, degrees):
    hw = float(width) / 2.0
    hh = float(height) / 2.0
    theta = math.radians(float(degrees))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    points = []
    for x, y in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        points.append((cx + x * cos_t - y * sin_t, cy + x * sin_t + y * cos_t))
    return points


def render_typecode_json(path, max_size=None):
    loaded = load_pillow()
    if not loaded:
        return None
    Image, ImageDraw = loaded
    try:
        shapes = _typecode_preview_shapes(path)
        if not shapes:
            return None
        margin = 64.0
        all_points = [point for item in shapes for polygon in item["polygons"] for point in polygon]
        min_x = min(point[0] for point in all_points) - margin
        max_x = max(point[0] for point in all_points) + margin
        min_y = min(point[1] for point in all_points) - margin
        max_y = max(point[1] for point in all_points) + margin
        image_w = max(1, int(math.ceil(max_x - min_x)))
        image_h = max(1, int(math.ceil(max_y - min_y)))
        scale = preview_scale(image_w, image_h, max_size)
        preview_w = max(1, int(round(image_w * scale)))
        preview_h = max(1, int(round(image_h * scale)))
        render_scale = scale * PREVIEW_JSON_SUPERSAMPLE
        render_w = max(1, preview_w * PREVIEW_JSON_SUPERSAMPLE)
        render_h = max(1, preview_h * PREVIEW_JSON_SUPERSAMPLE)
        background = Image.new("RGB", (render_w, render_h), (38, 38, 38))
        draw_bg = ImageDraw.Draw(background)
        tile = max(8, int(round(32 * render_scale)))
        for y in range(0, render_h, tile):
            for x in range(0, render_w, tile):
                if ((x // tile) + (y // tile)) % 2 == 0:
                    draw_bg.rectangle((x, y, min(render_w, x + tile), min(render_h, y + tile)), fill=(58, 58, 58))
        preview_layer = Image.new("RGBA", (render_w, render_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(preview_layer, "RGBA")
        for item in shapes:
            r, g, b, a = item["color"]
            if item.get("mask"):
                mask = Image.new("L", (render_w, render_h), 0)
                mask_draw = ImageDraw.Draw(mask)
                for polygon in item["polygons"]:
                    points = [((px - min_x) * render_scale, (py - min_y) * render_scale) for px, py in polygon]
                    mask_draw.polygon(points, fill=a)
                alpha = preview_layer.getchannel("A")
                alpha.paste(0, (0, 0), mask)
                preview_layer.putalpha(alpha)
                continue
            for polygon in item["polygons"]:
                points = [((px - min_x) * render_scale, (py - min_y) * render_scale) for px, py in polygon]
                draw.polygon(points, fill=(r, g, b, a))
        preview = background.convert("RGBA")
        preview.alpha_composite(preview_layer)
        preview = preview.convert("RGB")
        if PREVIEW_JSON_SUPERSAMPLE > 1:
            preview = preview.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
        return pil_to_photo(preview)
    except Exception:
        return None


def render_geometry_json(path, max_size=None):
    typecode_preview = render_typecode_json(path, max_size)
    if typecode_preview:
        return typecode_preview
    pillow_preview = render_geometry_json_pillow(path, max_size)
    if pillow_preview:
        return pillow_preview
    loaded = load_cv2()
    if not loaded:
        return None
    cv2, np = loaded
    try:
        data = load_normalized_geometry(path)
        shapes = data["shapes"]
        image_w, image_h = [int(v) for v in shapes[0]["data"][2:]]
        bg_r, bg_g, bg_b, bg_a = [int(v) for v in shapes[0]["color"]]
        scale = preview_scale(image_w, image_h, max_size)
        preview_w = max(1, int(round(image_w * scale)))
        preview_h = max(1, int(round(image_h * scale)))
        preview = np.zeros((preview_h, preview_w, 3), np.uint8)
        if bg_a > 0:
            preview[:, :] = (bg_b, bg_g, bg_r)
        else:
            preview[:, :] = (38, 38, 38)
            tile = max(8, int(round(32 * scale)))
            for y in range(0, preview_h, tile):
                for x in range(0, preview_w, tile):
                    if ((x // tile) + (y // tile)) % 2 == 0:
                        preview[y:y + tile, x:x + tile] = (58, 58, 58)
        for shape in shapes[1:]:
            color = [int(v) for v in shape.get("color", [])]
            if len(color) == 4 and color[3] <= 0:
                continue
            r, g, b, _a = color
            shape_type = int(shape.get("type", 0))
            if shape_type == ROTATED_ELLIPSE:
                x, y, w, h, rot_deg = shape["data"]
                center = (int(round(float(x) * scale)), int(round(float(y) * scale)))
                axes = (max(1, int(round(float(h) * scale))), max(1, int(round(float(w) * scale))))
                preview = cv2.ellipse(preview, center, axes, -90 + float(rot_deg), 0.0, 360.0, (b, g, r), thickness=-1)
            elif shape_type == RECTANGLE:
                x, y, w, h = shape["data"]
                x = float(x)
                y = float(y)
                w = float(w)
                h = float(h)
                x0 = int(round((x - w / 2) * scale))
                y0 = int(round((y - h / 2) * scale))
                x1 = int(round((x + w / 2) * scale))
                y1 = int(round((y + h / 2) * scale))
                preview = cv2.rectangle(preview, (x0, y0), (x1, y1), (b, g, r), thickness=-1)
        return image_to_photo(preview, max_size)
    except Exception:
        return None


def render_geometry_json_pillow(path, max_size=None):
    loaded = load_pillow()
    if not loaded:
        return None
    Image, ImageDraw = loaded
    try:
        data = load_normalized_geometry(path)
        shapes = data["shapes"]
        image_w, image_h = [int(v) for v in shapes[0]["data"][2:]]
        bg_r, bg_g, bg_b, bg_a = [int(v) for v in shapes[0]["color"]]
        scale = preview_scale(image_w, image_h, max_size)
        preview_w = max(1, int(round(image_w * scale)))
        preview_h = max(1, int(round(image_h * scale)))
        render_scale = scale * PREVIEW_JSON_SUPERSAMPLE
        render_w = max(1, preview_w * PREVIEW_JSON_SUPERSAMPLE)
        render_h = max(1, preview_h * PREVIEW_JSON_SUPERSAMPLE)
        if bg_a > 0:
            preview = Image.new("RGB", (render_w, render_h), (bg_r, bg_g, bg_b))
        else:
            preview = Image.new("RGB", (render_w, render_h), (38, 38, 38))
            draw_bg = ImageDraw.Draw(preview)
            tile = max(8, int(round(32 * render_scale)))
            for y in range(0, render_h, tile):
                for x in range(0, render_w, tile):
                    if ((x // tile) + (y // tile)) % 2 == 0:
                        draw_bg.rectangle((x, y, min(render_w, x + tile), min(render_h, y + tile)), fill=(58, 58, 58))
        draw = ImageDraw.Draw(preview)
        for shape in shapes[1:]:
            color = [int(v) for v in shape.get("color", [])]
            if len(color) == 4 and color[3] <= 0:
                continue
            r, g, b, _a = color
            shape_type = int(shape.get("type", 0))
            if shape_type == RECTANGLE:
                x, y, w, h = [float(v) for v in shape["data"]]
                x0 = int(round((x - w / 2) * render_scale))
                y0 = int(round((y - h / 2) * render_scale))
                x1 = int(round((x + w / 2) * render_scale))
                y1 = int(round((y + h / 2) * render_scale))
                draw.rectangle((x0, y0, x1, y1), fill=(r, g, b))
            elif shape_type == ROTATED_ELLIPSE:
                x, y, w, h, rot_deg = [float(v) for v in shape["data"]]
                draw_preview_ellipse_pillow(preview, x, y, w, h, rot_deg, (r, g, b), render_scale)
        if PREVIEW_JSON_SUPERSAMPLE > 1:
            preview = preview.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
        return pil_to_photo(preview)
    except Exception:
        return None


def draw_preview_ellipse_pillow(image, x, y, w, h, rot_deg, color, scale):
    # Match the historical OpenCV preview path used before the one-file EXE:
    # cv2.ellipse(..., axes=(h, w), angle=-90+rot).
    width, height = image.size
    cx = float(x) * scale
    cy = float(y) * scale
    rx = max(float(h) * scale, 1.0)
    ry = max(float(w) * scale, 1.0)
    theta = (-90.0 + float(rot_deg)) * (math.pi / 180.0)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    inv_rx2 = 1.0 / (rx * rx)
    inv_ry2 = 1.0 / (ry * ry)
    extent_x = math.sqrt(rx * rx * cos_t * cos_t + ry * ry * sin_t * sin_t)
    extent_y = math.sqrt(rx * rx * sin_t * sin_t + ry * ry * cos_t * cos_t)
    x_min = max(0, int(math.floor(cx - extent_x - 1)))
    x_max = min(width - 1, int(math.ceil(cx + extent_x + 1)))
    y_min = max(0, int(math.floor(cy - extent_y - 1)))
    y_max = min(height - 1, int(math.ceil(cy + extent_y + 1)))
    if x_min > x_max or y_min > y_max:
        return
    pixels = image.load()
    r, g, b = color
    for yy in range(y_min, y_max + 1):
        dy = (float(yy) + 0.5) - cy
        for xx in range(x_min, x_max + 1):
            dx = (float(xx) + 0.5) - cx
            xr = dx * cos_t + dy * sin_t
            yr = -dx * sin_t + dy * cos_t
            if xr * xr * inv_rx2 + yr * yr * inv_ry2 <= 1.0:
                pixels[xx, yy] = (r, g, b)


class App:
    def __init__(self, initial_images):
        ensure_dirs()
        self.root = Tk()
        self.root.title(app_title())
        self.root.geometry("1420x900")
        self.root.minsize(1180, 780)
        self.root.configure(bg=Theme.BG)
        self.lang = "en"
        self.queue = queue.Queue()
        self.shutdown_event = threading.Event()
        self.active_processes = set()
        self.process_lock = threading.Lock()
        self.generation_lock = threading.Lock()
        self.generation_running = False
        self.current_generator_proc = None
        self.eta_samples = deque(maxlen=ETA_MAX_PROGRESS_SAMPLES)
        self.eta_display_time = None
        self.eta_smoothed_seconds_per_layer = None
        self.eta_display_remaining = None
        self.eta_max_layer_seen = None
        self.eta_recycle_notice_active = False
        self.closed = False
        self.settings = load_settings()
        self.images = [Path(path) for path in initial_images if Path(path).exists()]
        self.json_files = []
        self.outputs = []
        self.processes = []
        self.photo = None
        self.use_custom_settings = StringVar(value="0")
        self.custom_stop_at = StringVar()
        self.custom_max_resolution = StringVar()
        self.custom_random_samples = StringVar()
        self.custom_mutated_samples = StringVar()
        self.custom_save_at = StringVar()
        self.custom_preprocess_mode = StringVar(value="none")
        self.translated = []
        self.detailed_log_lock = threading.Lock()
        self.detailed_log_lines = deque()
        self.detailed_log_chars = 0
        self.current_preview_request = None
        self.preview_resize_job = None
        self.preview_render_token = 0
        self.preview_cache = {}
        self.preview_last_schedule_key = None
        self.preview_display_cache_key = None
        self.update_state = {"status": "checking"}
        self.update_dialog = None
        self.update_check_started = False
        self.status = StringVar(value=tr(self.lang, "ready"))
        self.progress_text = StringVar(value="")
        self.selected_profile = StringVar()
        self.selected_game = StringVar(value="fh6")
        self.selected_pid = StringVar()
        self.layer_count = StringVar()
        self.snapshot_count = StringVar()
        self.current_count = StringVar()
        self.count_address = StringVar()
        self.table_address = StringVar()
        self.inspect_table_value = StringVar()
        self.runtime_folder = StringVar(value=str(ROOT))
        self.full_shape_count = StringVar(value="3000")
        self.full_shape_json_path = StringVar()
        self.full_shape_last_output_dir = StringVar(value=str(FULL_SHAPE_ROOT))
        self.full_shape_last_report_dir = StringVar()
        self.full_shape_clear_unused = StringVar(value="1")
        self.advanced_visible = False
        # Region Paint state
        self.region_images: list[Path] = []
        self.region_image_label_var = StringVar(value="")
        self._region_preview_showing: str = ""
        self.region_selected_profile = StringVar()
        self.region_total_var = StringVar(value="2000")
        self.region_first_var = StringVar(value="1000")
        self.region_layers_var = StringVar(value="300")
        self.region_remaining_var = StringVar(value="2000")
        self.region_tool = StringVar(value="rect")
        self.region_shapes: list[dict] = []
        self.region_selected_index: int | None = None
        self.region_rotation_var = IntVar(value=0)
        self.region_rotation_display = StringVar(value="0°")
        self.region_brush_size = IntVar(value=15)
        self.region_mask: "Image.Image | None" = None
        self.region_canvas_image_ref = None
        self.region_canvas_overlay_ref = None
        self._region_cached_pil = None       # cached full-res PIL image
        self._region_cached_pil_path = None  # path the cached image is for
        self._region_cached_display_pil = None  # cached resized display image
        self._region_cached_display_size = None  # (w, h) of the cached display image
        self.region_drag_start = None
        self.region_drag_mode: str | None = None  # "draw", "move", "rotate"
        self._region_move_snapshot: list[float] | None = None  # original coords when moving
        self._region_resize_corner: int | None = None  # 0=tl, 1=tr, 2=bl, 3=br
        self._region_resize_anchor_x: float = 0
        self._region_resize_anchor_y: float = 0
        self._region_handle_ids: list[int] = []  # tkinter canvas item IDs for rotation handle
        self.region_rubber_id = None
        self.region_poly_points: list[float] = []
        self.region_current_output_dir: str = ""
        self.region_workflow_running = False
        self.region_status = StringVar(value="Ready")
        self.region_progress = StringVar(value="")
        # Heatmap tab state
        self._region_right_tab: str = "preview"
        self.region_heatmap_ref = None
        self._region_heatmap_showing: str = ""
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_processes()
        if self.settings:
            self.selected_profile.set(self.settings[min(2, len(self.settings) - 1)]["label"])
            self._update_setting_description()
        for image_path in list(self.images):
            self._load_existing_checkpoints_for_image(image_path)
        self._render_lists()
        self.log_line(tr(self.lang, "runtime_location").format(runtime=ROOT / "runtime", probe=PROBE_DIR.parent))
        self._poll_queue()
        self.root.after(1000, self.start_update_check)

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", background=Theme.BG, foreground=Theme.TEXT, fieldbackground=Theme.INPUT)
        style.configure("TFrame", background=Theme.BG)
        style.configure("TNotebook", background=Theme.BG, borderwidth=0)
        style.configure("Primary.TNotebook", background=Theme.BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure(
            "Primary.TNotebook.Tab",
            padding=(18, 8),
            font=("Segoe UI", 10, "bold"),
            background=Theme.PANEL_ALT,
            foreground=Theme.MUTED,
            borderwidth=0,
        )
        style.map(
            "Primary.TNotebook.Tab",
            background=[("selected", Theme.ACCENT_DARK), ("active", Theme.PANEL_ALT)],
            foreground=[("selected", "#ffffff"), ("active", Theme.TEXT)],
        )
        style.configure(
            "TLabelframe",
            background=Theme.PANEL,
            foreground=Theme.TEXT,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
        )
        style.configure(
            "TLabelframe.Label",
            background=Theme.PANEL,
            foreground=Theme.TEXT,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "TCombobox",
            fieldbackground=Theme.INPUT,
            background=Theme.PANEL_ALT,
            foreground=Theme.TEXT,
            arrowcolor=Theme.TEXT,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Theme.INPUT)],
            foreground=[("readonly", Theme.TEXT)],
            selectbackground=[("readonly", Theme.ACCENT_DARK)],
            selectforeground=[("readonly", "#ffffff")],
        )
        style.configure(
            "TScrollbar",
            background=Theme.PANEL_ALT,
            troughcolor=Theme.BG,
            bordercolor=Theme.BORDER,
            arrowcolor=Theme.TEXT,
        )

    def _register_process(self, proc):
        with self.process_lock:
            self.active_processes.add(proc)

    def _popen_registered(self, cmd, **kwargs):
        # Hold process_lock across Popen + registration so on_close cannot miss
        # a child process that starts while the window is closing.
        with self.process_lock:
            if self.shutdown_event.is_set() or self.closed:
                return None
            proc = subprocess.Popen(cmd, **kwargs)
            self.active_processes.add(proc)
            return proc

    def _unregister_process(self, proc):
        with self.process_lock:
            self.active_processes.discard(proc)

    def _terminate_process(self, proc):
        if proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5,
                )
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _terminate_active_processes(self):
        with self.process_lock:
            processes = list(self.active_processes)
        for proc in processes:
            self._terminate_process(proc)

    def on_close(self):
        self.closed = True
        self.shutdown_event.set()
        self._terminate_active_processes()
        self.root.destroy()

    def _parent_bg(self, parent):
        try:
            return parent.cget("bg")
        except Exception:
            return Theme.PANEL

    def _label(self, parent, key, **kwargs):
        kwargs.setdefault("bg", self._parent_bg(parent))
        kwargs.setdefault("fg", Theme.TEXT)
        widget = Label(parent, text=tr(self.lang, key), **kwargs)
        self.translated.append((widget, key, "text"))
        return widget

    def _button(self, parent, key, command, **kwargs):
        kwargs.setdefault("bg", Theme.BUTTON)
        kwargs.setdefault("fg", Theme.TEXT)
        kwargs.setdefault("disabledforeground", Theme.MUTED)
        kwargs.setdefault("activebackground", Theme.BUTTON_ACTIVE)
        kwargs.setdefault("activeforeground", Theme.TEXT)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("highlightbackground", Theme.BORDER)
        kwargs.setdefault("highlightcolor", Theme.ACCENT)
        kwargs.setdefault("padx", 8)
        kwargs.setdefault("pady", 3)
        widget = Button(parent, text=tr(self.lang, key), command=command, **kwargs)
        self.translated.append((widget, key, "text"))
        return widget

    def _build_market_banner(self, parent):
        banner = Frame(parent, bg=Theme.ACCENT_DARK, highlightthickness=1, highlightbackground=Theme.ACCENT)
        banner._keep_custom_theme = True
        banner.pack(fill=X, padx=0, pady=(10, 0))
        message = Label(
            banner,
            text=tr(self.lang, "market_banner"),
            bg=Theme.ACCENT_DARK,
            fg="#ffffff",
            anchor="w",
            justify=LEFT,
            font=("Segoe UI", 11, "bold"),
        )
        message.pack(side=LEFT, fill=X, expand=True, padx=12, pady=8)
        self.translated.append((message, "market_banner", "text"))
        button = Button(
            banner,
            text=tr(self.lang, "open_market"),
            command=self.open_preset_market,
            bg=Theme.WARN,
            fg="#0d1117",
            activebackground="#ffe08a",
            activeforeground="#0d1117",
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        button.pack(side=RIGHT, padx=10, pady=8)
        self.translated.append((button, "open_market", "text"))
        return banner

    def open_preset_market(self):
        webbrowser.open(MARKET_URL)

    def _mapped_label_color(self, color):
        value = str(color or "").lower()
        if value in ("black", "#000000", "#000", "systembuttontext", "systemwindowtext"):
            return Theme.TEXT
        if value in ("systemdisabledtext", "gray", "grey", "gray40", "grey40"):
            return Theme.MUTED
        if value in ("#555", "#555555", "gray50", "grey50"):
            return Theme.MUTED
        if value in ("#005a9e", "blue"):
            return Theme.ACCENT
        if value in ("#8a5300", "orange", "darkorange"):
            return Theme.WARN
        return color if color else Theme.TEXT

    def _apply_dark_theme_recursive(self, widget):
        if getattr(widget, "_keep_custom_theme", False):
            return
        try:
            if isinstance(widget, Frame):
                bg = Theme.BG if widget.master is self.root else Theme.PANEL
                widget.configure(bg=bg)
            elif isinstance(widget, Label):
                if widget in (getattr(self, "preview_label", None), getattr(self, "import_preview_label", None)):
                    widget.configure(bg=Theme.INPUT, fg=Theme.TEXT)
                elif widget is getattr(self, "update_indicator", None):
                    widget.configure(bg=Theme.PANEL)
                else:
                    widget.configure(bg=self._parent_bg(widget.master), fg=self._mapped_label_color(widget.cget("fg")))
            elif isinstance(widget, Button):
                widget.configure(
                    bg=Theme.BUTTON,
                    fg=Theme.TEXT,
                    disabledforeground=Theme.MUTED,
                    activebackground=Theme.BUTTON_ACTIVE,
                    activeforeground=Theme.TEXT,
                    relief="flat",
                    bd=0,
                    highlightbackground=Theme.BORDER,
                    highlightcolor=Theme.ACCENT,
                )
            elif isinstance(widget, Checkbutton):
                widget.configure(
                    bg=self._parent_bg(widget.master),
                    fg=Theme.TEXT,
                    disabledforeground=Theme.MUTED,
                    activebackground=self._parent_bg(widget.master),
                    activeforeground=Theme.TEXT,
                    selectcolor=Theme.INPUT,
                    relief="flat",
                    highlightbackground=Theme.BORDER,
                    highlightcolor=Theme.ACCENT,
                )
            elif isinstance(widget, Entry):
                widget.configure(
                    bg=Theme.INPUT,
                    fg=Theme.TEXT,
                    insertbackground=Theme.TEXT,
                    disabledbackground=Theme.PANEL_ALT,
                    disabledforeground=Theme.MUTED,
                    readonlybackground=Theme.INPUT,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground=Theme.BORDER,
                    highlightcolor=Theme.ACCENT,
                )
            elif isinstance(widget, Listbox):
                widget.configure(
                    bg=Theme.INPUT,
                    fg=Theme.TEXT,
                    selectbackground=Theme.ACCENT_DARK,
                    selectforeground="#ffffff",
                    highlightthickness=1,
                    highlightbackground=Theme.BORDER,
                    relief="flat",
                )
            elif isinstance(widget, Text):
                widget.configure(
                    bg=Theme.INPUT,
                    fg=Theme.TEXT,
                    insertbackground=Theme.TEXT,
                    selectbackground=Theme.ACCENT_DARK,
                    selectforeground="#ffffff",
                    highlightthickness=1,
                    highlightbackground=Theme.BORDER,
                    relief="flat",
                )
            elif isinstance(widget, Canvas):
                widget.configure(bg=Theme.PANEL, highlightthickness=0)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._apply_dark_theme_recursive(child)

    def _build(self):
        self._configure_styles()
        header = Frame(self.root)
        header.pack(fill=X, padx=14, pady=(12, 6))

        # Title row: title on the left, language selector on the right
        title_row = Frame(header)
        title_row.pack(fill=X)
        self._label(title_row, "title", font=("Segoe UI", 18, "bold")).pack(side=LEFT)
        self.update_indicator = Label(
            title_row,
            text="",
            width=2,
            bg=Theme.BG,
            fg=Theme.WARN,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        )
        self.update_indicator.pack(side=RIGHT, padx=(8, 0))
        self.update_indicator.bind("<Button-1>", self.show_update_status)
        self.lang_combo = ttk.Combobox(title_row, values=list(LANGUAGES.keys()), state="readonly", width=10)
        self.lang_combo.set("English")
        self.lang_combo.pack(side=RIGHT)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)
        self._label(title_row, "language").pack(side=RIGHT, padx=(0, 6))

        # Subtitle row
        subtitle_row = Frame(header)
        subtitle_row.pack(fill=X)
        self._label(subtitle_row, "subtitle", fg=Theme.MUTED).pack(side=LEFT)

        process_bar = Frame(self.root)
        process_bar.pack(fill=X, padx=14, pady=(0, 8))
        self._label(process_bar, "process").pack(side=LEFT)
        self.process_combo = ttk.Combobox(process_bar, textvariable=self.selected_pid, state="readonly", width=44)
        self.process_combo.pack(side=LEFT, padx=8)
        self._button(process_bar, "refresh", self.refresh_processes).pack(side=LEFT)
        Label(process_bar, textvariable=self.status, anchor="e", bg=Theme.BG, fg=Theme.MUTED).pack(side=RIGHT)

        self.tabs = ttk.Notebook(self.root, style="Primary.TNotebook")
        self.generate_tab = Frame(self.tabs)
        self.import_tab = Frame(self.tabs)
        self.export_tab = Frame(self.tabs)
        self.region_paint_tab = Frame(self.tabs)
        self.tutorial_tab = Frame(self.tabs)
        self.tabs.add(self.generate_tab, text=tr(self.lang, "generate_tab"))
        self.tabs.add(self.import_tab, text=tr(self.lang, "import_tab"))
        self.tabs.add(self.export_tab, text=tr(self.lang, "export_tab"))
        self.tabs.add(self.region_paint_tab, text=tr(self.lang, "region_paint_tab"))
        self.tabs.add(self.tutorial_tab, text=tr(self.lang, "tutorial_tab"))

        self._build_generate_tab()
        self._build_import_tab()
        self._build_export_tab()
        self._build_region_paint_tab()
        self._build_tutorial_tab()
        # Pack log area BEFORE Notebook so side=BOTTOM widgets claim space first
        self._build_log()
        # Notebook fills remaining space between header/process-bar and log area
        self.tabs.pack(fill=BOTH, expand=True, padx=14, pady=(0, 8))
        self._apply_dark_theme_recursive(self.root)
        self.tabs.bind("<<NotebookTabChanged>>", self._schedule_preview_refresh)

    def _build_generate_tab(self):
        self._build_market_banner(self.generate_tab)
        left_outer = Frame(self.generate_tab)
        left_outer.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10), pady=10)
        right = Frame(self.generate_tab)
        right.pack(side=RIGHT, fill=BOTH, expand=True, pady=10)

        self._label(left_outer, "scroll_hint", anchor="w", justify=LEFT, fg="#8a5300").pack(fill=X, pady=(0, 6))
        scroll_area = Frame(left_outer)
        scroll_area.pack(fill=BOTH, expand=True, pady=(0, 8))
        left_canvas = Canvas(scroll_area, highlightthickness=0)
        left_scroll = ttk.Scrollbar(scroll_area, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        left_scroll.pack(side=RIGHT, fill="y")
        left = Frame(left_canvas)
        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")

        scroll_region_job = {"id": None}

        def _apply_scroll_region():
            scroll_region_job["id"] = None
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))

        def _update_scroll_region(_event=None):
            if scroll_region_job["id"] is not None:
                return
            scroll_region_job["id"] = left_canvas.after(LAYOUT_RESIZE_DEBOUNCE_MS, _apply_scroll_region)

        canvas_width_job = {"id": None, "width": None, "applied": None}

        def _apply_canvas_width():
            canvas_width_job["id"] = None
            width = canvas_width_job["width"]
            if not width or width == canvas_width_job["applied"]:
                return
            canvas_width_job["applied"] = width
            left_canvas.itemconfigure(left_window, width=width)

        def _match_canvas_width(event):
            width = max(1, int(event.width))
            bucket = max(1, LAYOUT_SIZE_BUCKET)
            width = max(1, int(round(width / bucket) * bucket))
            if width == canvas_width_job["width"] or width == canvas_width_job["applied"]:
                return
            canvas_width_job["width"] = width
            if canvas_width_job["id"] is not None:
                try:
                    left_canvas.after_cancel(canvas_width_job["id"])
                except Exception:
                    pass
            canvas_width_job["id"] = left_canvas.after(LAYOUT_RESIZE_DEBOUNCE_MS, _apply_canvas_width)

        def _mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(_event=None):
            left_canvas.bind_all("<MouseWheel>", _mousewheel)

        def _unbind_mousewheel(_event=None):
            left_canvas.unbind_all("<MouseWheel>")

        left.bind("<Configure>", _update_scroll_region)
        left_canvas.bind("<Configure>", _match_canvas_width)
        scroll_area.bind("<Enter>", _bind_mousewheel)
        scroll_area.bind("<Leave>", _unbind_mousewheel)

        step1 = ttk.LabelFrame(left, text=tr(self.lang, "generate_step_image"))
        self.translated.append((step1, "generate_step_image", "text"))
        step1.pack(fill=X, pady=(0, 6))
        row = Frame(step1)
        row.pack(fill=X, padx=10, pady=(6, 2))
        self._label(row, "images").pack(side=LEFT)
        self._button(row, "add_images", self.add_images).pack(side=RIGHT)
        self._button(row, "remove_image", self.remove_selected_image).pack(side=RIGHT, padx=8)
        self.image_list = Listbox(step1, height=3)
        self.image_list.pack(fill=X, padx=10, pady=(2, 8))
        self.image_list.bind("<<ListboxSelect>>", self._preview_selected_image)

        step2 = ttk.LabelFrame(left, text=tr(self.lang, "generate_step_quality"))
        self.translated.append((step2, "generate_step_quality", "text"))
        step2.pack(fill=X, pady=(0, 6))
        profile_row = Frame(step2)
        profile_row.pack(fill=X, padx=10, pady=(8, 4))
        self._label(profile_row, "quality").pack(side=LEFT)
        self.profile_combo = ttk.Combobox(
            profile_row,
            values=[item["label"] for item in self.settings],
            textvariable=self.selected_profile,
            state="readonly",
            width=32,
        )
        self.profile_combo.pack(side=LEFT, fill=X, expand=True, padx=(8, 0))
        self.profile_combo.bind("<<ComboboxSelected>>", self._update_setting_description)
        preset_actions = Frame(step2)
        preset_actions.pack(fill=X, padx=10, pady=(0, 6))
        self._button(preset_actions, "import_preset", self.import_preset).pack(side=LEFT)
        self._button(preset_actions, "open_preset_folder", self.open_preset_folder).pack(side=LEFT, padx=8)
        self.setting_description = Label(step2, text="", anchor="w", justify=LEFT, wraplength=500)
        self.setting_description.pack(fill=X, padx=10, pady=(0, 8))

        custom_section = ttk.LabelFrame(left, text=tr(self.lang, "custom_panel_title"))
        self.translated.append((custom_section, "custom_panel_title", "text"))
        custom_section.pack(fill=X, pady=(0, 6))
        self._label(custom_section, "custom_panel_hint", anchor="w", justify=LEFT, wraplength=540, fg="#005a9e").pack(fill=X, padx=10, pady=(6, 2))
        custom_toggle = Checkbutton(
            custom_section,
            text=tr(self.lang, "custom_settings"),
            variable=self.use_custom_settings,
            onvalue="1",
            offvalue="0",
            command=self._sync_custom_state,
        )
        custom_toggle.pack(anchor="w", padx=10, pady=(0, 2))
        self.translated.append((custom_toggle, "custom_settings", "text"))
        custom_grid = Frame(custom_section)
        custom_grid.pack(fill=X, padx=10, pady=(0, 6))
        self.custom_fields = []
        custom_specs = [
            ("custom_layers", self.custom_stop_at),
            ("custom_resolution", self.custom_max_resolution),
            ("custom_random", self.custom_random_samples),
            ("custom_mutated", self.custom_mutated_samples),
            ("custom_save_at", self.custom_save_at),
        ]
        for row_index, (key, variable) in enumerate(custom_specs):
            label = self._label(custom_grid, key, anchor="w")
            label.grid(row=row_index, column=0, sticky="w", pady=1, padx=(0, 8))
            entry = Entry(custom_grid, textvariable=variable, width=18)
            entry.grid(row=row_index, column=1, sticky="ew", pady=1)
            self.custom_fields.append(entry)
        custom_grid.columnconfigure(1, weight=1)
        preprocess_widget = self._field(custom_grid, "preprocess_mode", self.custom_preprocess_mode, row=len(custom_specs), values=["none", "luma_band"], readonly=True)
        self.custom_fields.append(preprocess_widget)
        custom_actions = Frame(custom_section)
        custom_actions.pack(fill=X, padx=10, pady=(0, 8))
        self._button(custom_actions, "save_custom_preset", self.save_custom_preset).pack(side=LEFT)
        self._sync_custom_state()

        step3 = ttk.LabelFrame(left_outer, text=tr(self.lang, "generate_step_run"))
        self.translated.append((step3, "generate_step_run", "text"))
        step3.pack(fill=X)
        self._label(step3, "generate_step_run_hint", anchor="w", justify=LEFT, wraplength=540).pack(fill=X, padx=10, pady=(8, 4))
        actions = Frame(step3)
        actions.pack(fill=X, padx=10, pady=(4, 12))
        self.generate_button = self._button(actions, "start_generate", self.start_generate, font=("Segoe UI", 12, "bold"), height=2)
        self.generate_button.pack(side=LEFT, fill=X, expand=True)
        self.stop_generate_button = self._button(actions, "stop_generate", self.stop_generate, height=2, state="disabled")
        self.stop_generate_button.pack(side=LEFT, padx=8)
        self._button(actions, "open_output", self.open_output_folder, height=2).pack(side=LEFT)

        preview_header = Frame(right)
        preview_header.pack(fill=X)
        self._label(preview_header, "preview", anchor="w", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
        self._label(preview_header, "preview_accuracy_note", anchor="e", justify=RIGHT, fg=Theme.WARN, wraplength=420).pack(side=RIGHT, fill=X, expand=True)
        self.preview_label = Label(right, text=tr(self.lang, "preview_hint"), bg="#202020", fg="#dddddd", width=60, height=24)
        self.preview_label.pack(fill=BOTH, expand=True, pady=6)
        self.preview_label.bind("<Configure>", self._schedule_preview_refresh)

    def _build_region_paint_tab(self):
        """Build the Region Paint tab with image selection, budget, tools, and preview canvas."""
        # --- Left panel (scrollable controls) ---
        left_outer = Frame(self.region_paint_tab)
        left_outer.pack(side=LEFT, fill=BOTH, expand=False, padx=(0, 10), pady=10)

        scroll_area = Frame(left_outer)
        scroll_area.pack(fill=BOTH, expand=True, pady=(0, 8))
        left_canvas = Canvas(scroll_area, highlightthickness=0, width=380)
        left_scroll = ttk.Scrollbar(scroll_area, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        left_scroll.pack(side=RIGHT, fill="y")
        left = Frame(left_canvas)
        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")

        def _apply_region_scroll_region():
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))

        def _update_region_scroll_region(_event=None):
            left_canvas.after(LAYOUT_RESIZE_DEBOUNCE_MS, _apply_region_scroll_region)

        def _match_region_canvas_width(event):
            width = max(1, int(event.width))
            bucket = max(1, LAYOUT_SIZE_BUCKET)
            width = max(1, int(round(width / bucket) * bucket))
            left_canvas.itemconfigure(left_window, width=width)

        def _region_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_region_mousewheel(_event=None):
            left_canvas.bind_all("<MouseWheel>", _region_mousewheel)

        def _unbind_region_mousewheel(_event=None):
            left_canvas.unbind_all("<MouseWheel>")

        left.bind("<Configure>", _update_region_scroll_region)
        left_canvas.bind("<Configure>", _match_region_canvas_width)
        scroll_area.bind("<Enter>", _bind_region_mousewheel)
        scroll_area.bind("<Leave>", _unbind_region_mousewheel)

        # Step 1 — Image & Profile
        step1 = ttk.LabelFrame(left, text=tr(self.lang, "region_step_image"))
        self.translated.append((step1, "region_step_image", "text"))
        step1.pack(fill=X, pady=(0, 6))
        row = Frame(step1)
        row.pack(fill=X, padx=10, pady=(6, 2))
        self._label(row, "images").pack(side=LEFT)
        self._button(row, "add_images", self.region_add_image).pack(side=RIGHT)
        Label(step1, textvariable=self.region_image_label_var, anchor="w", bg=self._parent_bg(step1), fg=Theme.MUTED, wraplength=350).pack(fill=X, padx=10, pady=(2, 4))
        profile_row = Frame(step1)
        profile_row.pack(fill=X, padx=10, pady=(0, 8))
        self._label(profile_row, "quality").pack(side=LEFT)
        self.region_profile_combo = ttk.Combobox(
            profile_row,
            values=[item["label"] for item in self.settings],
            textvariable=self.region_selected_profile,
            state="readonly",
            width=26,
        )
        self.region_profile_combo.pack(side=LEFT, fill=X, expand=True, padx=(8, 0))
        self.region_profile_combo.bind("<<ComboboxSelected>>", self._region_update_profile_description)
        if self.settings:
            self.region_selected_profile.set(self.settings[min(2, len(self.settings) - 1)]["label"])
        self.region_profile_description = Label(step1, text="", anchor="w", justify=LEFT, wraplength=350, bg=self._parent_bg(step1), fg=Theme.MUTED)
        self.region_profile_description.pack(fill=X, padx=10, pady=(0, 8))

        # Step 2 — Budget
        step2 = ttk.LabelFrame(left, text=tr(self.lang, "region_step_budget"))
        self.translated.append((step2, "region_step_budget", "text"))
        step2.pack(fill=X, pady=(0, 6))
        budget_grid = Frame(step2)
        budget_grid.pack(fill=X, padx=10, pady=(8, 8))
        for ri, (key, var) in enumerate([
            ("region_total_layers", self.region_total_var),
            ("region_first_pass_layers", self.region_first_var),
            ("region_region_layers", self.region_layers_var),
        ]):
            self._label(budget_grid, key, anchor="w").grid(row=ri, column=0, sticky="w", pady=1, padx=(0, 8))
            Entry(budget_grid, textvariable=var, width=10).grid(row=ri, column=1, sticky="ew", pady=1)
        rem_row = Frame(step2)
        rem_row.pack(fill=X, padx=10, pady=(0, 8))
        self._label(rem_row, "region_remaining").pack(side=LEFT)
        Label(rem_row, textvariable=self.region_remaining_var, fg=Theme.ACCENT, bg=self._parent_bg(rem_row)).pack(side=LEFT, padx=6)

        # Step 3 — Selection Tools
        step3 = ttk.LabelFrame(left, text=tr(self.lang, "region_step_selection"))
        self.translated.append((step3, "region_step_selection", "text"))
        step3.pack(fill=X, pady=(0, 6))
        tool_row = Frame(step3)
        tool_row.pack(fill=X, padx=10, pady=(8, 4))
        tools = [
            ("region_tool_rect", "rect"),
            ("region_tool_ellipse", "ellipse"),
        ]
        for key, value in tools:
            btn = Button(
                tool_row,
                text=tr(self.lang, key),
                command=lambda v=value: self._region_set_tool(v),
                relief="flat", bd=1, padx=6, pady=2,
                font=("Segoe UI", 9),
            )
            btn.pack(side=LEFT, padx=2)
            self.translated.append((btn, key, "text"))
        self._button(tool_row, "region_tool_clear", self._region_clear_mask).pack(side=LEFT, padx=(8, 2))
        self._button(tool_row, "region_tool_clear_selected", self._region_clear_selected_mask).pack(side=LEFT, padx=2)

        # Rotation control (visible when a shape is selected)
        rot_row = Frame(step3)
        rot_row.pack(fill=X, padx=10, pady=(0, 8))
        rot_label = Label(rot_row, text=tr(self.lang, "region_rotation"), bg=self._parent_bg(rot_row))
        rot_label.pack(side=LEFT)
        self.translated.append((rot_label, "region_rotation", "text"))
        self.region_rotation_slider = ttk.Scale(
            rot_row, from_=-180, to=180, orient="horizontal",
            variable=self.region_rotation_var, state="disabled",
            command=self._region_on_rotation_changed,
        )
        self.region_rotation_slider.pack(side=LEFT, fill=X, expand=True, padx=6)
        self.region_rotation_label = Entry(
            rot_row, textvariable=self.region_rotation_display,
            bg=Theme.INPUT, fg=Theme.TEXT, insertbackground=Theme.ACCENT,
            width=5, justify="right", state="disabled",
            relief="solid", bd=1,
        )
        self.region_rotation_label.pack(side=LEFT)
        self.region_rotation_label.bind("<Return>", self._region_rotation_entry_apply)
        self.region_rotation_label.bind("<FocusOut>", self._region_rotation_entry_apply)

        # Duplicate result buttons inside scrollable area for small screens
        hint_row = Frame(step3)
        hint_row.pack(fill=X, padx=10, pady=(2, 0))
        hint_label = Label(hint_row, text=tr(self.lang, "region_small_screen_hint"),
                           bg=self._parent_bg(hint_row), fg=Theme.MUTED, font=("Segoe UI", 8))
        hint_label.pack(side=LEFT)
        self.translated.append((hint_label, "region_small_screen_hint", "text"))
        dup_row = Frame(step3)
        dup_row.pack(fill=X, padx=10, pady=(2, 6))
        self.region_open_folder_btn2 = self._button(dup_row, "region_open_result_folder", self._region_open_result_folder, state="disabled")
        self.region_open_folder_btn2.pack(side=LEFT, fill=X, expand=True)
        self.region_save_json_btn2 = self._button(dup_row, "region_save_result_json", self._region_save_result_json, state="disabled")
        self.region_save_json_btn2.pack(side=LEFT, padx=6, fill=X, expand=True)

        # Step 4 — Actions
        step4 = ttk.LabelFrame(left_outer, text=tr(self.lang, "region_step_actions"))
        self.translated.append((step4, "region_step_actions", "text"))
        step4.pack(fill=X)
        actions = Frame(step4)
        actions.pack(fill=X, padx=10, pady=(8, 4))
        self.region_first_pass_btn = self._button(actions, "region_start_first_pass", self._region_start_first_pass, font=("Segoe UI", 11, "bold"), height=2)
        self.region_first_pass_btn.pack(side=LEFT, fill=X, expand=True)
        self.region_paint_btn = self._button(actions, "region_paint_region", self._region_start_pass, height=2, state="disabled")
        self.region_paint_btn.pack(side=LEFT, padx=6, fill=X, expand=True)
        self.region_stop_btn = self._button(actions, "region_stop", self._region_stop, height=2, state="disabled")
        self.region_stop_btn.pack(side=LEFT, padx=6)
        status_row = Frame(step4)
        status_row.pack(fill=X, padx=10, pady=(0, 8))
        Label(status_row, textvariable=self.region_status, fg=Theme.MUTED, bg=self._parent_bg(status_row), anchor="w", wraplength=180).pack(side=LEFT)
        Label(status_row, textvariable=self.region_progress, fg=Theme.ACCENT, bg=self._parent_bg(status_row), font=("Segoe UI", 9), anchor="e", wraplength=180).pack(side=RIGHT)

        # Pass History
        hist = ttk.LabelFrame(left_outer, text=tr(self.lang, "region_pass_history"))
        self.translated.append((hist, "region_pass_history", "text"))
        hist.pack(fill=X, pady=(6, 0))
        self.region_pass_list = Listbox(hist, height=4)
        self.region_pass_list.pack(fill=X, padx=10, pady=(4, 8))

        # Result actions
        result_row = Frame(left_outer)
        result_row.pack(fill=X, pady=(4, 0))
        self.region_open_folder_btn = self._button(result_row, "region_open_result_folder", self._region_open_result_folder, state="disabled")
        self.region_open_folder_btn.pack(side=LEFT, fill=X, expand=True)
        self.region_save_json_btn = self._button(result_row, "region_save_result_json", self._region_save_result_json, state="disabled")
        self.region_save_json_btn.pack(side=LEFT, padx=6, fill=X, expand=True)

        # --- Right panel (Canvas) ---
        right = Frame(self.region_paint_tab)
        right.pack(side=RIGHT, fill=BOTH, expand=True, pady=10)
        # Labels above canvases
        canvas_label_row = Frame(right)
        canvas_label_row.pack(fill=X)
        self._label(canvas_label_row, "region_original_label", anchor="w").pack(side=LEFT, expand=True, fill=X)
        # Tab bar replacing static "Preview" label
        tab_row = Frame(canvas_label_row, bg=self._parent_bg(canvas_label_row))
        tab_row.pack(side=LEFT, expand=True, fill=X)
        self.region_tab_preview_btn = Label(
            tab_row, text=tr(self.lang, "region_preview_tab"), anchor="w",
            bg=Theme.INPUT, fg=Theme.TEXT, padx=8, pady=2,
            cursor="hand2",
        )
        self.region_tab_preview_btn.pack(side=LEFT)
        self.region_tab_preview_btn.bind("<Button-1>", lambda e: self._region_switch_tab("preview"))
        self.region_tab_heatmap_btn = Label(
            tab_row, text=tr(self.lang, "region_heatmap_tab"), anchor="w",
            bg=Theme.BUTTON, fg=Theme.MUTED, padx=8, pady=2,
            cursor="arrow",
        )
        self.region_tab_heatmap_btn.pack(side=LEFT)
        self.region_tab_heatmap_btn.bind("<Button-1>", lambda e: self._region_switch_tab("heatmap"))
        self.translated.append((self.region_tab_preview_btn, "region_preview_tab", "text"))
        self.translated.append((self.region_tab_heatmap_btn, "region_heatmap_tab", "text"))
        # Canvases side by side
        canvas_row = Frame(right)
        canvas_row.pack(fill=BOTH, expand=True, pady=6)
        self.region_canvas_left = Canvas(canvas_row, bg=Theme.INPUT, highlightthickness=1, highlightbackground=Theme.BORDER, cursor="cross")
        self.region_canvas_left.pack(side=LEFT, fill=BOTH, expand=True)
        self.region_canvas_right = Canvas(canvas_row, bg=Theme.INPUT, highlightthickness=1, highlightbackground=Theme.BORDER)
        self.region_canvas_right.pack(side=LEFT, fill=BOTH, expand=True)
        # Backwards compatibility alias — selection tools use left canvas
        self.region_canvas = self.region_canvas_left

        # Canvas bindings for selection tools
        self.region_canvas.bind("<Button-1>", self._region_canvas_press)
        self.region_canvas.bind("<B1-Motion>", self._region_canvas_drag)
        self.region_canvas.bind("<ButtonRelease-1>", self._region_canvas_release)
        self.region_canvas.bind("<Double-Button-1>", self._region_canvas_double_click)
        self.region_canvas.bind("<Motion>", self._region_canvas_motion)
        self.region_canvas.bind("<Configure>", self._region_canvas_configure)
        self.region_canvas_right.bind("<Configure>", self._region_canvas_configure)
        # Scroll wheel to rotate selected shape
        self.region_canvas.bind("<MouseWheel>", self._region_on_mousewheel)
        self.region_canvas.bind("<Button-4>", self._region_on_mousewheel)
        self.region_canvas.bind("<Button-5>", self._region_on_mousewheel)

        if self.settings:
            self._region_update_profile_description()  # sync stopAt → total budget
        self._region_update_button_states()

    # ==================================================================
    # Region Paint — Canvas configure (persist preview on resize)
    # ==================================================================

    def _region_canvas_configure(self, _event=None):
        """Redraw the image/preview when canvases resize."""
        self._region_cached_display_pil = None  # invalidate display cache on resize
        self._region_cached_display_size = None
        if self.region_workflow_running:
            return
        # Redraw original image on left canvas if an image is selected
        if self.region_images:
            if getattr(self, "_region_configure_image_job", None):
                self.region_canvas_left.after_cancel(self._region_configure_image_job)
            self._region_configure_image_job = self.region_canvas_left.after(
                200, lambda: self._region_display_image(self.region_images[0])
            )
        # Redraw right canvas based on active tab
        if self._region_right_tab == "heatmap":
            heatmap = getattr(self, "_region_heatmap_showing", None)
            if heatmap and Path(heatmap).exists():
                if getattr(self, "_region_configure_heatmap_job", None):
                    self.region_canvas_right.after_cancel(self._region_configure_heatmap_job)
                self._region_configure_heatmap_job = self.region_canvas_right.after(
                    200, lambda: self._region_display_heatmap(Path(heatmap))
                )
        else:
            preview = getattr(self, "_region_preview_showing", None)
            if preview and Path(preview).exists():
                if getattr(self, "_region_configure_preview_job", None):
                    self.region_canvas_right.after_cancel(self._region_configure_preview_job)
                self._region_configure_preview_job = self.region_canvas_right.after(
                    200, lambda: self._region_display_preview(Path(preview))
                )

    # ==================================================================
    # Region Paint — Image management
    # ==================================================================

    def region_add_image(self):
        paths = filedialog.askopenfilenames(
            title=tr(self.lang, "add_images"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")],
        )
        if not paths:
            return
        # Only keep the last selected image — replace any existing image.
        pp = Path(paths[-1])
        if not pp.exists():
            return
        self.region_images.clear()
        self.region_images.append(pp)
        self._region_clear_mask()
        self._region_update_image_label()
        self._region_display_image(pp)

    def _region_update_image_label(self):
        """Update the image label to show the current image path."""
        if self.region_images:
            self.region_image_label_var.set(str(self.region_images[0]))
        else:
            self.region_image_label_var.set("")
        self._region_update_button_states()

    def _region_display_image(self, image_path: Path):
        """Load and display an image on the LEFT region canvas."""
        try:
            from PIL import Image, ImageTk
            # Cache the full-res image so redraws avoid disk I/O.
            if self._region_cached_pil is None or self._region_cached_pil_path != image_path:
                self._region_cached_pil = Image.open(image_path).convert("RGBA")
                self._region_cached_pil_path = image_path
                self._region_cached_display_pil = None  # invalidate display cache
                self._region_cached_display_size = None
            img = self._region_cached_pil.copy()
            cw = self.region_canvas_left.winfo_width() or 300
            ch = self.region_canvas_left.winfo_height() or 500
            display_size = min(cw - 4, ch - 4, 600)
            ratio = display_size / max(img.width, img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            self.region_canvas_image_ref = ImageTk.PhotoImage(img)
            self.region_canvas_left.delete("all")
            self.region_canvas_left.create_image(2, 2, anchor="nw", image=self.region_canvas_image_ref)
            self._region_redraw_overlay()
        except Exception as e:
            self.log_line(f"Region Paint: failed to load image: {e}")

    # ==================================================================
    # Region Paint — Canvas mouse handlers
    # ==================================================================

    def _region_set_tool(self, tool: str):
        self.region_tool.set(tool)
        self.region_canvas.configure(cursor="cross")

    def _region_get_canvas_scale(self) -> float:
        """Compute scale factor: canvas-display-pixels / working-pixels."""
        if not self.region_images:
            return 1.0
        try:
            if self._region_cached_pil is not None:
                w, h = self._region_cached_pil.size
            else:
                from PIL import Image
                img = Image.open(self.region_images[0])
                w, h = img.size
            display_w = max(1, (self.region_canvas.winfo_width() or 600) - 4)
            display_h = max(1, (self.region_canvas.winfo_height() or 500) - 4)
            display_size = min(display_w, display_h, 600)
            ratio = display_size / max(w, h)
            return ratio  # canvas_pixels / working_pixels
        except Exception:
            return 1.0

    def _region_hit_test(self, x: float, y: float) -> int | None:
        """Return the index of the shape at canvas point (x, y), or None.
        Tests shapes in reverse order so the top-most shape wins."""
        import math
        for i in range(len(self.region_shapes) - 1, -1, -1):
            shape = self.region_shapes[i]
            tool = shape.get("tool", "")
            coords = shape.get("coords", [])
            if tool not in ("rect", "ellipse") or len(coords) < 4:
                continue
            cx = (coords[0] + coords[2]) / 2.0
            cy = (coords[1] + coords[3]) / 2.0
            hw = abs(coords[2] - coords[0]) / 2.0
            hh = abs(coords[3] - coords[1]) / 2.0
            rotation = shape.get("rotation", 0)
            # Transform point into shape-local (unrotated) space
            if rotation != 0:
                rad = math.radians(-rotation)
                cos_r, sin_r = math.cos(rad), math.sin(rad)
                dx = x - cx
                dy = y - cy
                lx = dx * cos_r - dy * sin_r
                ly = dx * sin_r + dy * cos_r
            else:
                lx = x - cx
                ly = y - cy
            if tool == "rect":
                if abs(lx) <= hw and abs(ly) <= hh:
                    return i
            else:  # ellipse
                if hw > 0 and hh > 0:
                    if (lx * lx) / (hw * hw) + (ly * ly) / (hh * hh) <= 1.0:
                        return i
        return None

    def _region_hit_test_handle(self, x: float, y: float) -> bool:
        """Return True if point (x, y) is on the rotation handle of the selected shape."""
        if self.region_selected_index is None or self.region_selected_index >= len(self.region_shapes):
            return False
        shape = self.region_shapes[self.region_selected_index]
        coords = shape.get("coords", [])
        if len(coords) < 4:
            return False
        import math
        cx = (coords[0] + coords[2]) / 2.0
        cy = (coords[1] + coords[3]) / 2.0
        hh = abs(coords[3] - coords[1]) / 2.0
        rotation = shape.get("rotation", 0)
        rad = math.radians(rotation)
        handle_offset = 14
        hx = cx + math.sin(rad) * (hh + handle_offset)
        hy = cy - math.cos(rad) * (hh + handle_offset)
        return math.hypot(x - hx, y - hy) <= 8

    def _region_hit_test_resize(self, x: float, y: float) -> int | None:
        """Return corner index (0=tl, 1=tr, 2=bl, 3=br) if (x,y) is on a resize handle."""
        if self.region_selected_index is None or self.region_selected_index >= len(self.region_shapes):
            return None
        shape = self.region_shapes[self.region_selected_index]
        coords = shape.get("coords", [])
        if len(coords) < 4:
            return None
        import math
        cx = (coords[0] + coords[2]) / 2.0
        cy = (coords[1] + coords[3]) / 2.0
        rotation = shape.get("rotation", 0)
        rad = math.radians(rotation)
        corners = [
            (coords[0], coords[1]),
            (coords[2], coords[1]),
            (coords[0], coords[3]),
            (coords[2], coords[3]),
        ]
        for i, (ux, uy) in enumerate(corners):
            dx = ux - cx
            dy = uy - cy
            rx = cx + dx * math.cos(rad) - dy * math.sin(rad)
            ry = cy + dx * math.sin(rad) + dy * math.cos(rad)
            if abs(x - rx) <= 5 and abs(y - ry) <= 5:
                return i
        return None

    def _region_canvas_press(self, event):
        tool = self.region_tool.get()
        if tool not in ("rect", "ellipse"):
            return

        # 1. If a shape is selected, check for rotation-handle click
        if self.region_selected_index is not None:
            if self._region_hit_test_handle(event.x, event.y):
                self.region_drag_mode = "rotate"
                self.region_drag_start = (event.x, event.y)
                return

            # 1b. Check for resize-handle click
            corner = self._region_hit_test_resize(event.x, event.y)
            if corner is not None:
                self.region_drag_mode = "resize"
                self.region_drag_start = (event.x, event.y)
                self._region_resize_corner = corner
                # Store opposite corner as anchor
                shape = self.region_shapes[self.region_selected_index]
                coords = shape["coords"]
                opposite = {0: 3, 1: 2, 2: 1, 3: 0}[corner]
                opp_corners = [
                    (coords[0], coords[1]),
                    (coords[2], coords[1]),
                    (coords[0], coords[3]),
                    (coords[2], coords[3]),
                ]
                self._region_resize_anchor_x = opp_corners[opposite][0]
                self._region_resize_anchor_y = opp_corners[opposite][1]
                return

        # 2. Check if clicking on any shape body
        hit = self._region_hit_test(event.x, event.y)
        if hit is not None:
            # Select and prepare for move
            self.region_selected_index = hit
            shape = self.region_shapes[hit]
            angle = shape.get("rotation", 0)
            self.region_rotation_var.set(angle)
            self.region_rotation_display.set(f"{angle}°")
            self.region_rotation_slider.config(state="normal")
            self.region_rotation_label.config(state="normal")
            self.region_drag_mode = "move"
            self.region_drag_start = (event.x, event.y)
            self._region_move_snapshot = list(shape["coords"])
            self._region_redraw_overlay()
            return

        # 3. Click on empty space — deselect and prepare for new-shape drag
        self.region_selected_index = None
        self.region_rotation_var.set(0)
        self.region_rotation_display.set("0°")
        self.region_rotation_slider.config(state="disabled")
        self.region_rotation_label.config(state="disabled")
        self.region_drag_mode = "draw"
        self.region_drag_start = (event.x, event.y)
        self._region_redraw_overlay()

    def _region_canvas_drag(self, event):
        import math

        if self.region_drag_mode == "move":
            if self.region_selected_index is not None and self._region_move_snapshot:
                dx = event.x - self.region_drag_start[0]
                dy = event.y - self.region_drag_start[1]
                orig = self._region_move_snapshot
                self.region_shapes[self.region_selected_index]["coords"] = [
                    orig[0] + dx, orig[1] + dy,
                    orig[2] + dx, orig[3] + dy,
                ]
                self._region_redraw_overlay()
            return

        if self.region_drag_mode == "rotate":
            if self.region_selected_index is not None:
                shape = self.region_shapes[self.region_selected_index]
                coords = shape["coords"]
                cx = (coords[0] + coords[2]) / 2.0
                cy = (coords[1] + coords[3]) / 2.0
                angle = math.degrees(math.atan2(event.x - cx, -(event.y - cy)))
                angle = round(angle)
                # Normalize to [-180, 180]
                angle = ((angle + 180) % 360) - 180
                shape["rotation"] = angle
                self.region_rotation_var.set(angle)
                self.region_rotation_display.set(f"{angle}°")
                self._region_redraw_overlay()
            return

        if self.region_drag_mode == "resize":
            if self.region_selected_index is not None and self._region_resize_corner is not None:
                shape = self.region_shapes[self.region_selected_index]
                coords = shape["coords"]
                cx = (coords[0] + coords[2]) / 2.0
                cy = (coords[1] + coords[3]) / 2.0
                rotation = shape.get("rotation", 0)
                # Unrotate mouse position into shape-local space
                if rotation != 0:
                    rad_inv = math.radians(-rotation)
                    dx = event.x - cx
                    dy = event.y - cy
                    lx = cx + dx * math.cos(rad_inv) - dy * math.sin(rad_inv)
                    ly = cy + dx * math.sin(rad_inv) + dy * math.cos(rad_inv)
                else:
                    lx, ly = event.x, event.y
                anchor_x = self._region_resize_anchor_x
                anchor_y = self._region_resize_anchor_y
                corner = self._region_resize_corner
                if corner == 0:      # tl
                    x1, y1, x2, y2 = lx, ly, anchor_x, anchor_y
                elif corner == 1:    # tr
                    x1, y1, x2, y2 = anchor_x, ly, lx, anchor_y
                elif corner == 2:    # bl
                    x1, y1, x2, y2 = lx, anchor_y, anchor_x, ly
                else:                # br
                    x1, y1, x2, y2 = anchor_x, anchor_y, lx, ly
                # Enforce ordering and minimum size
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
                if x2 - x1 < 6:
                    mid = (x1 + x2) / 2
                    x1, x2 = mid - 3, mid + 3
                if y2 - y1 < 6:
                    mid = (y1 + y2) / 2
                    y1, y2 = mid - 3, mid + 3
                shape["coords"] = [x1, y1, x2, y2]
                self._region_redraw_overlay()
            return

        # Draw mode — existing rubberband logic
        tool = self.region_tool.get()
        if self.region_drag_start:
            x1, y1 = self.region_drag_start
            if self.region_rubber_id:
                self.region_canvas.delete(self.region_rubber_id)
            if tool == "rect":
                self.region_rubber_id = self.region_canvas.create_rectangle(
                    x1, y1, event.x, event.y, outline="#ff4444", dash=(4, 2))
            elif tool == "ellipse":
                self.region_rubber_id = self.region_canvas.create_oval(
                    x1, y1, event.x, event.y, outline="#ff4444", dash=(4, 2))

    def _region_canvas_release(self, event):
        if self.region_drag_mode == "move":
            self.region_drag_mode = None
            self._region_move_snapshot = None
            self.region_drag_start = None
            self._region_redraw_overlay()
            self._region_update_button_states()
            return

        if self.region_drag_mode == "rotate":
            self.region_drag_mode = None
            self.region_drag_start = None
            self._region_redraw_overlay()
            self._region_update_button_states()
            return

        if self.region_drag_mode == "resize":
            self.region_drag_mode = None
            self.region_drag_start = None
            self._region_resize_corner = None
            self._region_redraw_overlay()
            self._region_update_button_states()
            return

        # Draw mode — existing logic
        tool = self.region_tool.get()
        if tool in ("rect", "ellipse") and self.region_drag_start:
            x1, y1 = self.region_drag_start
            x2, y2 = event.x, event.y
            if abs(x2 - x1) > 3 and abs(y2 - y1) > 3:
                # Normalize so x1<=x2, y1<=y2 regardless of drag direction
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
                self.region_shapes.append({"tool": tool, "coords": [x1, y1, x2, y2], "rotation": 0})
            if self.region_rubber_id:
                self.region_canvas.delete(self.region_rubber_id)
                self.region_rubber_id = None
            self.region_drag_start = None
            self._region_redraw_overlay()
        self.region_drag_mode = None
        self._region_update_button_states()

    def _region_canvas_double_click(self, event):
        pass  # no-op (polygon removed)

    def _region_canvas_motion(self, _event):
        """Cursor preview (no-op for now, could show crosshair)."""
        pass

    def _region_redraw_overlay(self):
        """Redraw the red semi-transparent mask overlay on the canvas.
        Supports rotated shapes via OpenCV; falls back to PIL for axis-aligned."""
        try:
            from PIL import Image, ImageDraw, ImageTk
        except Exception:
            return
        if not self.region_images:
            return
        image_path = self.region_images[0]
        # Use cached full-res image to avoid disk I/O.
        if self._region_cached_pil is None or self._region_cached_pil_path != image_path:
            self._region_cached_pil = Image.open(image_path).convert("RGBA")
            self._region_cached_pil_path = image_path
        img = self._region_cached_pil
        cw = self.region_canvas.winfo_width() or 600
        ch = self.region_canvas.winfo_height() or 500
        display_size = min(cw - 4, ch - 4, 600)
        ratio = display_size / max(img.width, img.height)
        new_w = max(1, int(img.width * ratio))
        new_h = max(1, int(img.height * ratio))
        # Use cached display-size image when canvas size hasn't changed
        cur_display = (new_w, new_h)
        if self._region_cached_display_pil is not None and self._region_cached_display_size == cur_display:
            img = self._region_cached_display_pil
        else:
            img = img.copy().resize((new_w, new_h), Image.LANCZOS)
            self._region_cached_display_pil = img
            self._region_cached_display_size = cur_display
        # Draw red overlay for each shape
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        # Try OpenCV for rotated shapes
        loaded = load_cv2()
        if loaded:
            cv2, np = loaded
            # Build overlay as numpy (H, W, 4) uint8
            overlay_np = np.zeros((new_h, new_w, 4), dtype=np.uint8)
            for i, shape in enumerate(self.region_shapes):
                tool = shape.get("tool", "")
                coords = shape.get("coords", [])
                if tool not in ("rect", "ellipse") or len(coords) < 4:
                    continue
                x1, y1, x2, y2 = [float(c) for c in coords[:4]]
                if x1 > x2:
                    x1, x2 = x2, x1
                if y1 > y2:
                    y1, y2 = y2, y1
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                hw = (x2 - x1) / 2.0
                hh = (y2 - y1) / 2.0
                rotation = shape.get("rotation", 0)
                is_selected = (i == self.region_selected_index)
                fill_color = (0, 0, 255, 100) if is_selected else (0, 0, 255, 80)  # BGR+A in cv2 space → RGBA later
                # Note: cv2 uses BGR order, we'll convert later
                if tool == "rect":
                    if rotation != 0:
                        # Rotated rectangle via boxPoints
                        rect = ((cx, cy), (hw * 2, hh * 2), rotation)
                        box = cv2.boxPoints(rect).astype(np.int32)
                        cv2.fillPoly(overlay_np, [box], fill_color)
                    else:
                        cv2.rectangle(overlay_np,
                                      (int(x1), int(y1)), (int(x2), int(y2)),
                                      fill_color, thickness=-1)
                else:  # ellipse
                    # cv2.ellipse: axes are (semi-major, semi-minor), use (hw, hh)
                    cv2.ellipse(overlay_np,
                                (int(cx), int(cy)), (int(hw), int(hh)),
                                rotation, 0.0, 360.0,
                                fill_color, thickness=-1)
                # Draw selection highlight outline
                if is_selected:
                    outline_color = (255, 255, 0, 255)  # Yellow outline
                    if tool == "rect" and rotation != 0:
                        rect = ((cx, cy), (hw * 2, hh * 2), rotation)
                        box = cv2.boxPoints(rect).astype(np.int32)
                        cv2.polylines(overlay_np, [box], isClosed=True, color=outline_color, thickness=2)
                    elif tool == "rect":
                        cv2.rectangle(overlay_np, (int(x1), int(y1)), (int(x2), int(y2)),
                                      outline_color, thickness=2)
                    else:
                        cv2.ellipse(overlay_np, (int(cx), int(cy)), (int(hw), int(hh)),
                                    rotation, 0.0, 360.0, outline_color, thickness=2)
            # Convert numpy (BGRA) → PIL RGBA overlay
            # cv2 uses BGRA, PIL uses RGBA: swap R and B channels
            overlay_np_rgba = np.zeros_like(overlay_np)
            overlay_np_rgba[:, :, 0] = overlay_np[:, :, 2]  # R ← B
            overlay_np_rgba[:, :, 1] = overlay_np[:, :, 1]  # G ← G
            overlay_np_rgba[:, :, 2] = overlay_np[:, :, 0]  # B ← R
            overlay_np_rgba[:, :, 3] = overlay_np[:, :, 3]  # A ← A
            overlay = Image.fromarray(overlay_np_rgba, "RGBA")
        else:
            # Fallback: PIL axis-aligned only (legacy path)
            draw = ImageDraw.Draw(overlay)
            for i, shape in enumerate(self.region_shapes):
                tool = shape.get("tool", "")
                coords = shape.get("coords", [])
                if tool in ("rect", "ellipse") and len(coords) >= 4:
                    x1, y1, x2, y2 = [int(c) for c in coords[:4]]
                    x1, x2 = sorted([x1, x2])
                    y1, y2 = sorted([y1, y2])
                    is_selected = (i == self.region_selected_index)
                    fill = (255, 0, 0, 100) if is_selected else (255, 0, 0, 80)
                    if tool == "rect":
                        draw.rectangle([x1, y1, x2, y2], fill=fill)
                    else:
                        draw.ellipse([x1, y1, x2, y2], fill=fill)
                    if is_selected:
                        draw.rectangle([x1, y1, x2, y2], outline=(255, 255, 0), width=2)
        img = Image.alpha_composite(img, overlay)
        self.region_canvas_image_ref = ImageTk.PhotoImage(img)
        self.region_canvas.delete("all")
        self.region_canvas.create_image(2, 2, anchor="nw", image=self.region_canvas_image_ref)

        # Draw rotation handle on canvas for the selected shape
        if self.region_selected_index is not None and self.region_selected_index < len(self.region_shapes):
            shape = self.region_shapes[self.region_selected_index]
            coords = shape.get("coords", [])
            if len(coords) >= 4:
                import math
                cx = (coords[0] + coords[2]) / 2.0
                cy = (coords[1] + coords[3]) / 2.0
                hh = abs(coords[3] - coords[1]) / 2.0
                rotation = shape.get("rotation", 0)
                rad = math.radians(rotation)
                handle_offset = 14
                hx = cx + math.sin(rad) * (hh + handle_offset)
                hy = cy - math.cos(rad) * (hh + handle_offset)
                r = 5
                lid = self.region_canvas.create_line(cx, cy, hx, hy, fill="#ffff00", width=1, tags=("rot_handle",))
                cid = self.region_canvas.create_oval(hx - r, hy - r, hx + r, hy + r,
                                                     fill="#ffff00", outline="#000000", width=1,
                                                     tags=("rot_handle",))
                self._region_handle_ids = [lid, cid]

                # Draw corner resize handles
                hw = abs(coords[2] - coords[0]) / 2.0
                # 4 unrotated corners: tl, tr, bl, br
                corners = [
                    (coords[0], coords[1]),
                    (coords[2], coords[1]),
                    (coords[0], coords[3]),
                    (coords[2], coords[3]),
                ]
                corner_tags = ("rsz_tl", "rsz_tr", "rsz_bl", "rsz_br")
                rs = 3  # half-size of resize handle square
                for i, (ux, uy) in enumerate(corners):
                    # Rotate around center
                    dx = ux - cx
                    dy = uy - cy
                    rx = cx + dx * math.cos(rad) - dy * math.sin(rad)
                    ry = cy + dx * math.sin(rad) + dy * math.cos(rad)
                    rid = self.region_canvas.create_rectangle(
                        rx - rs, ry - rs, rx + rs, ry + rs,
                        fill="#ffffff", outline="#000000", width=1,
                        tags=("resize_handle", corner_tags[i]),
                    )
                    self._region_handle_ids.append(rid)

    def _region_on_rotation_changed(self, _value=None):
        """Callback when the rotation slider is moved."""
        if self.region_drag_mode == "rotate":
            return  # Canvas handle manages rotation; avoid double update
        if self.region_selected_index is not None and self.region_selected_index < len(self.region_shapes):
            angle = int(float(self.region_rotation_var.get()))
            self.region_shapes[self.region_selected_index]["rotation"] = angle
            self.region_rotation_display.set(f"{angle}°")
            self._region_redraw_overlay()

    def _region_rotation_entry_apply(self, _event=None):
        """Apply the angle typed into the rotation entry box."""
        if self.region_selected_index is None:
            return
        try:
            raw = self.region_rotation_display.get().replace("°", "").strip()
            angle = int(float(raw))
            angle = max(-180, min(180, angle))
            self.region_rotation_var.set(angle)
        except (ValueError, TypeError):
            # Restore to current shape's rotation on invalid input
            current = self.region_shapes[self.region_selected_index].get("rotation", 0)
            self.region_rotation_display.set(f"{current}°")

    def _region_on_mousewheel(self, event):
        """Scroll wheel rotates the selected shape by +/-5 degrees."""
        if self.region_selected_index is None:
            return
        if self.region_selected_index >= len(self.region_shapes):
            return
        # Determine direction: Windows uses event.delta, Linux uses event.num
        if hasattr(event, "delta"):
            delta = 1 if event.delta > 0 else -1
        elif hasattr(event, "num"):
            delta = 1 if event.num == 4 else -1
        else:
            return
        shape = self.region_shapes[self.region_selected_index]
        current = shape.get("rotation", 0)
        step = 1 if (event.state & 0x0001) else 5  # Shift held = fine (1 deg), else coarse (5 deg)
        new_angle = current + delta * step
        # Clamp to [-180, 180]
        new_angle = max(-180, min(180, new_angle))
        shape["rotation"] = new_angle
        self.region_rotation_var.set(new_angle)
        self.region_rotation_display.set(f"{new_angle}°")
        self._region_redraw_overlay()

    def _region_clear_mask(self):
        self.region_shapes.clear()
        self.region_poly_points.clear()
        self.region_drag_start = None
        self.region_drag_mode = None
        self._region_move_snapshot = None
        self._region_resize_corner = None
        self.region_selected_index = None
        self.region_rotation_var.set(0)
        self.region_rotation_display.set("0°")
        self.region_rotation_slider.config(state="disabled")
        self.region_rotation_label.config(state="disabled")
        if self.region_rubber_id:
            self.region_canvas.delete(self.region_rubber_id)
            self.region_rubber_id = None
        self.region_mask = None
        if self.region_images:
            self._region_display_image(self.region_images[0])
        self._region_update_button_states()

    def _region_clear_selected_mask(self):
        """Clear only the currently selected mask shape."""
        if self.region_selected_index is None:
            self.log_line("Region Paint: No mask selected. Click a mask on the canvas to select it first.")
            return
        idx = self.region_selected_index
        if idx < 0 or idx >= len(self.region_shapes):
            self.log_line("Region Paint: Selected mask no longer exists.")
            return
        del self.region_shapes[idx]
        self.region_selected_index = None
        self.region_rotation_var.set(0)
        self.region_rotation_display.set("0°")
        self.region_rotation_slider.config(state="disabled")
        self.region_rotation_label.config(state="disabled")
        self._region_redraw_overlay()
        self._region_update_button_states()

    def _region_generate_mask(self) -> "Image.Image | None":
        """Convert canvas shapes to a PIL 'L' mask at working resolution."""
        if not self.region_shapes or not self.region_images:
            return None
        try:
            from PIL import Image
            img = Image.open(self.region_images[0])
            w, h = img.size
            scale = self._region_get_canvas_scale()
            from region_painter.image_processor import mask_from_canvas_shapes
            mask = mask_from_canvas_shapes(self.region_shapes, w, h, scale)
            return mask
        except Exception as e:
            self.log_line(f"Region Paint: mask generation failed: {e}")
            return None

    # ==================================================================
    # Region Paint — Button state management
    # ==================================================================

    def _region_update_button_states(self):
        has_image = bool(self.region_images)
        has_shapes = bool(self.region_shapes)
        running = self.region_workflow_running
        has_output = bool(self.region_current_output_dir)
        self.region_first_pass_btn.config(state="normal" if has_image and not running else "disabled")
        self.region_paint_btn.config(state="normal" if has_image and has_shapes and not running else "disabled")
        self.region_stop_btn.config(state="normal" if running else "disabled")
        enabled = "normal" if has_output and not running else "disabled"
        self.region_open_folder_btn.config(state=enabled)
        self.region_save_json_btn.config(state=enabled)
        self.region_open_folder_btn2.config(state=enabled)
        self.region_save_json_btn2.config(state=enabled)
        # Heatmap tab: only clickable when a heatmap exists
        has_heatmap = bool(self._region_heatmap_showing)
        if self.region_tab_heatmap_btn:
            if has_heatmap or self._region_right_tab == "heatmap":
                self.region_tab_heatmap_btn.config(cursor="hand2")
            else:
                self.region_tab_heatmap_btn.config(cursor="arrow")
        # Update remaining from saved state if available, else from entries
        if self.region_current_output_dir:
            try:
                status = region_get_status(self.region_current_output_dir)
                self.region_remaining_var.set(str(status.get("remaining", 0)))
                return
            except Exception:
                pass
        try:
            total = int(self.region_total_var.get() or 0)
            self.region_remaining_var.set(str(total))
        except ValueError:
            self.region_remaining_var.set("0")

    def _region_update_profile_description(self, _event=None):
        """Show the selected profile's description and sync total budget."""
        label = self.region_selected_profile.get()
        item = next((s for s in self.settings if s["label"] == label), None)
        desc = item["description"] if item else ""
        self.region_profile_description.config(text=desc)
        # Sync total budget from profile's stopAt
        if item:
            stop_at = item.get("values", {}).get("stopAt", "")
            if stop_at:
                self.region_total_var.set(stop_at)
                self._region_update_button_states()

    # ==================================================================
    # Region Paint — Result actions
    # ==================================================================

    def _region_open_result_folder(self):
        """Open the current output directory in the file manager."""
        if not self.region_current_output_dir:
            return
        folder = Path(self.region_current_output_dir)
        if folder.exists():
            os.startfile(folder)
            self.log_line(f"Region Paint: opened result folder — {folder}")

    def _region_save_result_json(self):
        """Save base.json from the current output directory to a user-chosen location."""
        if not self.region_current_output_dir:
            return
        base_json = Path(self.region_current_output_dir) / "base.json"
        if not base_json.exists():
            self.log_line("Region Paint: result JSON not found. Run a pass first.")
            return
        output = filedialog.asksaveasfilename(
            title="Save result JSON",
            initialdir=str(Path(self.region_current_output_dir)),
            initialfile="base.json",
            defaultextension=".json",
            filetypes=[("Geometry JSON", "*.json"), ("All files", "*.*")],
        )
        if not output:
            return
        try:
            shutil.copy2(base_json, output)
            self.log_line(f"Region Paint: result JSON saved — {output}")
        except OSError as exc:
            self.log_line(f"Region Paint: failed to save result JSON: {exc}")

    # ==================================================================
    # Region Paint — Worker threads
    # ==================================================================

    def _region_start_first_pass(self):
        if not self.region_images:
            self.log_line(tr(self.lang, "region_no_image"))
            return
        image_path = self.region_images[0]
        profile_label = self.region_selected_profile.get()
        setting = next((s for s in self.settings if s["label"] == profile_label), None)
        if setting is None and self.settings:
            setting = self.settings[0]
        if setting is None:
            self.log_line("No quality profile selected.")
            return
        try:
            total_budget = int(self.region_total_var.get() or 2000)
            first_layers = int(self.region_first_var.get() or 1000)
        except ValueError:
            self.log_line("Invalid budget values.")
            return
        if first_layers > total_budget:
            self.log_line(f"Region Paint: First-pass layers ({first_layers}) exceed total budget ({total_budget}). Please adjust the values.")
            return
        output_dir = ROOT / "runtime" / "region-painter" / f"{image_path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.region_current_output_dir = str(output_dir)
        self.region_workflow_running = True
        # state.json does not exist yet — show total budget as remaining
        self.region_remaining_var.set(str(total_budget))
        self._region_update_button_states()
        self.region_status.set(tr(self.lang, "running"))
        self.region_progress.set("Starting first pass...")
        self.log_line("Region Paint: first pass starting...")
        threading.Thread(
            target=self._region_first_pass_worker,
            args=(image_path, setting, first_layers, output_dir),
            daemon=True,
        ).start()

    def _region_first_pass_worker(self, image_path: Path, setting, first_layers: int, output_dir: Path):
        """Worker thread: prepare, run exe (streaming), finalize."""
        def on_progress(msg):
            self.queue.put(("region_log", msg))
            self.queue.put(("region_progress", msg))
        try:
            prep = prepare_first_pass(
                image_path=str(image_path),
                settings_path=str(setting["path"]),
                first_layers=first_layers,
                output_dir=str(output_dir),
                on_progress=on_progress,
            )
            if "error" in prep:
                self.queue.put(("region_done", {"ok": False, "error": prep["error"]}))
                return

            # --- Run exe with streaming (same pattern as _generate_worker) ---
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = self._popen_registered(
                prep["cmd"],
                cwd=str(output_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                env=build_generator_env(),
            )
            if proc is None:
                self.queue.put(("region_done", {"ok": False, "error": "Shutdown"}))
                return
            with self.generation_lock:
                self.current_generator_proc = proc

            output_queue = queue.Queue()

            def _reader():
                try:
                    for raw_line in proc.stdout:
                        output_queue.put(raw_line)
                finally:
                    output_queue.put(None)

            reader = threading.Thread(target=_reader, daemon=True)
            reader.start()

            # --- Poll for exe preview files (same pattern as _generate_worker) ---
            last_preview_mtime = None
            next_preview_scan = 0.0

            try:
                while proc.poll() is None:
                    if self.shutdown_event.is_set():
                        self._terminate_process(proc)
                        self.queue.put(("region_done", {"ok": False, "error": "Stopped"}))
                        return
                    while True:
                        try:
                            raw = output_queue.get_nowait()
                        except queue.Empty:
                            break
                        if raw is None:
                            continue
                        stripped = raw.strip()
                        if stripped:
                            friendly = self.friendly_generator_line(stripped)
                            if friendly:
                                self.queue.put(("region_log", friendly))
                    # --- Preview polling ---
                    now = time.monotonic()
                    if now >= next_preview_scan:
                        next_preview_scan = now + GENERATOR_PREVIEW_SCAN_SECONDS
                        preview_files = sorted(
                            output_dir.glob("_exe_preview*.png"),
                            key=lambda p: p.stat().st_mtime, reverse=True,
                        )
                        if preview_files:
                            newest = preview_files[0]
                            try:
                                mtime = newest.stat().st_mtime
                            except OSError:
                                mtime = None
                            if mtime is not None and mtime != last_preview_mtime:
                                last_preview_mtime = mtime
                                self.queue.put(("region_preview", str(newest)))
                    time.sleep(GENERATOR_POLL_SLEEP_SECONDS)
                reader.join(timeout=1)
            finally:
                self._unregister_process(proc)
                with self.generation_lock:
                    if self.current_generator_proc is proc:
                        self.current_generator_proc = None

            if proc.returncode != 0:
                self.queue.put(("region_log", f"Generator exited with code {proc.returncode}"))
                self.queue.put(("region_done", {"ok": False, "error": f"Exit code {proc.returncode}"}))
                return

            result = finalize_first_pass(prep)
            result["preview_path"] = prep.get("preview_png", "")
            # Generate heatmap from the resulting geometry JSON
            try:
                base_json = Path(prep["base_json"])
                if base_json.exists():
                    heatmap_png = base_json.parent / "heatmap.png"
                    from scripts.heatmap import generate_standalone_heatmap
                    generate_standalone_heatmap(base_json, heatmap_png)
                    result["heatmap_path"] = str(heatmap_png)
            except Exception as hm_err:
                self.queue.put(("region_log", f"Heatmap generation skipped: {hm_err}"))
            self.queue.put(("region_done", result))
        except Exception as e:
            self.queue.put(("region_status", tr(self.lang, "failed")))
            self.queue.put(("region_log", f"First pass error: {e}"))
            self.queue.put(("region_done", {"ok": False, "error": str(e)}))

    def _region_start_pass(self):
        if self.region_workflow_running:
            self.log_line("Region Paint: already running, ignoring duplicate request.")
            return
        if not self.region_shapes:
            self.log_line(tr(self.lang, "region_no_mask"))
            return
        mask = self._region_generate_mask()
        if mask is None:
            self.log_line("Failed to generate selection mask.")
            return
        try:
            region_layers = int(self.region_layers_var.get() or 300)
        except ValueError:
            region_layers = 300
        output_dir = Path(self.region_current_output_dir)
        state = StateManager(output_dir)
        if state.is_first_pass_done and state.used_layers + region_layers > state.total_budget:
            self.log_line(f"Region Paint: Current layers ({state.used_layers}) + region layers ({region_layers}) exceed total budget ({state.total_budget}). Please adjust the values.")
            return
        self.region_workflow_running = True
        self._region_update_button_states()
        self.region_status.set(tr(self.lang, "running"))
        self.region_progress.set("Starting region pass...")
        self.log_line("Region Paint: region pass starting...")
        threading.Thread(
            target=self._region_pass_worker,
            args=(output_dir, region_layers, mask),
            daemon=True,
        ).start()

    def _region_pass_worker(self, output_dir: Path, region_layers: int, mask):
        """Worker thread: prepare, run exe (streaming), finalize."""
        def on_progress(msg):
            self.queue.put(("region_log", msg))
            self.queue.put(("region_progress", msg))
        try:
            prep = prepare_region_pass(
                output_dir=str(output_dir),
                region_layers=region_layers,
                selection_mask=mask,
                on_progress=on_progress,
            )
            if "error" in prep:
                self.queue.put(("region_done", {"ok": False, "error": prep["error"]}))
                return

            # --- Run exe with streaming (same pattern as _generate_worker) ---
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = self._popen_registered(
                prep["cmd"],
                cwd=str(output_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                env=build_generator_env(),
            )
            if proc is None:
                self.queue.put(("region_done", {"ok": False, "error": "Shutdown"}))
                return
            with self.generation_lock:
                self.current_generator_proc = proc

            output_queue = queue.Queue()

            def _reader():
                try:
                    for raw_line in proc.stdout:
                        output_queue.put(raw_line)
                finally:
                    output_queue.put(None)

            reader = threading.Thread(target=_reader, daemon=True)
            reader.start()

            # --- Poll for exe preview files ---
            last_preview_mtime = None
            next_preview_scan = 0.0

            try:
                while proc.poll() is None:
                    if self.shutdown_event.is_set():
                        self._terminate_process(proc)
                        self.queue.put(("region_done", {"ok": False, "error": "Stopped"}))
                        return
                    while True:
                        try:
                            raw = output_queue.get_nowait()
                        except queue.Empty:
                            break
                        if raw is None:
                            continue
                        stripped = raw.strip()
                        if stripped:
                            friendly = self.friendly_generator_line(stripped)
                            if friendly:
                                self.queue.put(("region_log", friendly))
                    # --- Preview polling ---
                    now = time.monotonic()
                    if now >= next_preview_scan:
                        next_preview_scan = now + GENERATOR_PREVIEW_SCAN_SECONDS
                        preview_files = sorted(
                            output_dir.glob("_exe_preview*.png"),
                            key=lambda p: p.stat().st_mtime, reverse=True,
                        )
                        if preview_files:
                            newest = preview_files[0]
                            try:
                                mtime = newest.stat().st_mtime
                            except OSError:
                                mtime = None
                            if mtime is not None and mtime != last_preview_mtime:
                                last_preview_mtime = mtime
                                self.queue.put(("region_preview", str(newest)))
                    time.sleep(GENERATOR_POLL_SLEEP_SECONDS)
                reader.join(timeout=1)
            finally:
                self._unregister_process(proc)
                with self.generation_lock:
                    if self.current_generator_proc is proc:
                        self.current_generator_proc = None

            if proc.returncode != 0:
                self.queue.put(("region_log", f"Generator exited with code {proc.returncode}"))
                self.queue.put(("region_done", {"ok": False, "error": f"Exit code {proc.returncode}"}))
                return

            result = finalize_region_pass(prep)
            result["preview_path"] = prep.get("preview_png", "")
            # Generate heatmap from the resulting geometry JSON
            try:
                base_json = Path(prep["base_json"])
                if base_json.exists():
                    heatmap_png = base_json.parent / "heatmap.png"
                    from scripts.heatmap import generate_standalone_heatmap
                    generate_standalone_heatmap(base_json, heatmap_png)
                    result["heatmap_path"] = str(heatmap_png)
            except Exception as hm_err:
                self.queue.put(("region_log", f"Heatmap generation skipped: {hm_err}"))
            self.queue.put(("region_done", result))
        except Exception as e:
            self.queue.put(("region_status", tr(self.lang, "failed")))
            self.queue.put(("region_log", f"Region pass error: {e}"))
            self.queue.put(("region_done", {"ok": False, "error": str(e)}))

    def _region_stop(self):
        self.shutdown_event.set()
        self.region_status.set(tr(self.lang, "stopped"))
        self.region_workflow_running = False
        self._region_update_button_states()

    def _region_display_preview(self, preview_path: Path):
        """Display a rendered preview image on the RIGHT region canvas."""
        try:
            from PIL import Image, ImageTk
            img = Image.open(preview_path).convert("RGBA")
            cw = self.region_canvas_right.winfo_width() or 300
            ch = self.region_canvas_right.winfo_height() or 500
            display_size = min(cw - 4, ch - 4, 600)
            ratio = display_size / max(img.width, img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            self.region_preview_ref = ImageTk.PhotoImage(img)
            self.region_canvas_right.delete("all")
            self.region_canvas_right.create_image(2, 2, anchor="nw", image=self.region_preview_ref)
            self._region_preview_showing = str(preview_path)
        except Exception:
            pass

    def _region_display_heatmap(self, heatmap_path: Path):
        """Display a heatmap image on the RIGHT region canvas."""
        try:
            from PIL import Image, ImageTk
            img = Image.open(heatmap_path).convert("RGB")
            cw = self.region_canvas_right.winfo_width() or 300
            ch = self.region_canvas_right.winfo_height() or 500
            display_size = min(cw - 4, ch - 4, 600)
            ratio = display_size / max(img.width, img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            self.region_heatmap_ref = ImageTk.PhotoImage(img)
            self.region_canvas_right.delete("all")
            self.region_canvas_right.create_image(2, 2, anchor="nw", image=self.region_heatmap_ref)
            self._region_heatmap_showing = str(heatmap_path)
        except Exception:
            pass

    def _region_switch_tab(self, tab_name: str):
        """Switch the right-canvas tab between 'preview' and 'heatmap'."""
        if self.region_workflow_running:
            return
        if tab_name == self._region_right_tab:
            return
        # Prevent switching to heatmap if no heatmap exists yet
        if tab_name == "heatmap" and not self._region_heatmap_showing:
            return
        self._region_right_tab = tab_name
        # Update button styles
        if tab_name == "preview":
            self.region_tab_preview_btn.config(bg=Theme.INPUT, fg=Theme.TEXT)
            self.region_tab_heatmap_btn.config(
                bg=Theme.BUTTON,
                fg=Theme.TEXT if self._region_heatmap_showing else Theme.MUTED,
            )
            preview = getattr(self, "_region_preview_showing", None)
            if preview and Path(preview).exists():
                self._region_display_preview(Path(preview))
            else:
                self.region_canvas_right.delete("all")
        else:  # heatmap
            self.region_tab_heatmap_btn.config(bg=Theme.INPUT, fg=Theme.TEXT)
            self.region_tab_preview_btn.config(bg=Theme.BUTTON, fg=Theme.TEXT)
            heatmap = getattr(self, "_region_heatmap_showing", None)
            if heatmap and Path(heatmap).exists():
                self._region_display_heatmap(Path(heatmap))
            else:
                self.region_canvas_right.delete("all")

    def _build_import_tab(self):
        self._build_market_banner(self.import_tab)
        left = Frame(self.import_tab)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10), pady=10)
        right = Frame(self.import_tab)
        right.pack(side=RIGHT, fill=BOTH, expand=True, pady=10)

        step1 = ttk.LabelFrame(left, text=tr(self.lang, "step_game"))
        self.translated.append((step1, "step_game", "text"))
        step1.pack(fill=X, pady=(0, 10))
        self._label(step1, "step_game_hint", anchor="w", justify=LEFT, wraplength=540).pack(fill=X, padx=10, pady=(8, 4))
        game_row = Frame(step1)
        game_row.pack(fill=X, padx=10, pady=(0, 10))
        self._label(game_row, "game_profile").pack(side=LEFT)
        self.import_game_combo = ttk.Combobox(game_row, values=list(PROFILES.keys()), textvariable=self.selected_game, state="readonly", width=8)
        self.import_game_combo.pack(side=LEFT, padx=8)
        self._label(game_row, "pid").pack(side=LEFT)
        self.import_pid_entry = Entry(game_row, textvariable=self.selected_pid, width=30)
        self.import_pid_entry.pack(side=LEFT, padx=8)
        self._button(game_row, "refresh", self.refresh_processes).pack(side=LEFT)

        step2 = ttk.LabelFrame(left, text=tr(self.lang, "step_template"))
        self.translated.append((step2, "step_template", "text"))
        step2.pack(fill=X, pady=(0, 10))
        self._label(step2, "step_template_hint", anchor="w", justify=LEFT, wraplength=540).pack(fill=X, padx=10, pady=(8, 4))
        template_row = Frame(step2)
        template_row.pack(fill=X, padx=10, pady=(0, 10))
        self._label(template_row, "layer_count").pack(side=LEFT)
        self.layer_count_entry = Entry(template_row, textvariable=self.layer_count, width=18, font=("Segoe UI", 13))
        self.layer_count_entry.pack(side=LEFT, padx=8)

        step3 = ttk.LabelFrame(left, text=tr(self.lang, "step_json"))
        self.translated.append((step3, "step_json", "text"))
        step3.pack(fill=BOTH, expand=True, pady=(0, 10))
        self._label(step3, "step_json_hint", anchor="w", justify=LEFT, wraplength=540).pack(fill=X, padx=10, pady=(8, 4))
        row = Frame(step3)
        row.pack(fill=X, padx=10)
        self._label(row, "json_files").pack(side=LEFT)
        self._button(row, "add_json", self.add_json).pack(side=RIGHT)
        self._button(row, "remove_json", self.remove_selected_json).pack(side=RIGHT, padx=(8, 0))
        self._button(row, "use_outputs", self.use_generated_outputs).pack(side=RIGHT, padx=8)
        self.json_list = Listbox(step3, height=10)
        self.json_list.pack(fill=BOTH, expand=True, padx=10, pady=6)
        self.json_list.bind("<<ListboxSelect>>", self._preview_selected_json)

        step4 = ttk.LabelFrame(right, text=tr(self.lang, "step_import"))
        self.translated.append((step4, "step_import", "text"))
        step4.pack(fill=X, pady=(0, 10))
        self._label(step4, "step_import_hint", anchor="w", justify=LEFT, wraplength=500).pack(fill=X, padx=10, pady=(8, 4))
        self._label(step4, "easy_import_hint", anchor="w", justify=LEFT, wraplength=500, fg="#555").pack(fill=X, padx=10, pady=4)
        self._label(step4, "admin_note", anchor="w", justify=LEFT, wraplength=500, fg="#8a5300").pack(fill=X, padx=10, pady=4)
        actions = Frame(step4)
        actions.pack(fill=X, padx=10, pady=12)
        self._button(actions, "import_json", self.start_import, font=("Segoe UI", 13, "bold"), height=2).pack(side=LEFT, fill=X, expand=True)
        self.advanced_button = self._button(actions, "show_advanced", self.toggle_advanced)
        self.advanced_button.pack(side=LEFT, padx=(8, 0))

        self.advanced_frame = ttk.LabelFrame(right, text=tr(self.lang, "advanced_options"))
        self.translated.append((self.advanced_frame, "advanced_options", "text"))
        self._field(self.advanced_frame, "manual_count", self.count_address, row=0)
        self._field(self.advanced_frame, "manual_table", self.table_address, row=1)
        self._button(self.advanced_frame, "auto_locate", self.start_auto_locate).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 4))

        import_preview_header = Frame(right)
        import_preview_header.pack(fill=X, pady=(8, 0))
        self._label(import_preview_header, "import_preview", anchor="w", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
        self._label(import_preview_header, "preview_accuracy_note", anchor="e", justify=RIGHT, fg=Theme.WARN, wraplength=420).pack(side=RIGHT, fill=X, expand=True)
        self.import_preview_label = Label(right, text=tr(self.lang, "preview_hint"), bg="#202020", fg="#dddddd", width=56, height=20)
        self.import_preview_label.pack(fill=BOTH, expand=True, pady=6)
        self.import_preview_label.bind("<Configure>", self._schedule_preview_refresh)

    def _build_export_tab(self):
        self._build_market_banner(self.export_tab)
        left = Frame(self.export_tab)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10), pady=10)
        right = Frame(self.export_tab)
        right.pack(side=RIGHT, fill=BOTH, expand=True, pady=10)

        intro = ttk.LabelFrame(left, text=tr(self.lang, "full_shape_intro_title"))
        self.translated.append((intro, "full_shape_intro_title", "text"))
        intro.pack(fill=X, pady=(0, 10))
        self._label(intro, "full_shape_intro", anchor="w", justify=LEFT, wraplength=560, fg=Theme.WARN).pack(fill=X, padx=10, pady=8)

        session = ttk.LabelFrame(left, text=tr(self.lang, "full_shape_session_title"))
        self.translated.append((session, "full_shape_session_title", "text"))
        session.pack(fill=X, pady=(0, 10))
        self._label(session, "full_shape_session_hint", anchor="w", justify=LEFT, wraplength=560).pack(fill=X, padx=10, pady=(8, 4))
        session_row = Frame(session)
        session_row.pack(fill=X, padx=10, pady=(0, 10))
        self._label(session_row, "pid").pack(side=LEFT)
        Entry(session_row, textvariable=self.selected_pid, width=32).pack(side=LEFT, padx=8)
        self._button(session_row, "refresh", self.refresh_processes).pack(side=LEFT)
        self._label(session_row, "layer_count").pack(side=LEFT, padx=(14, 0))
        Entry(session_row, textvariable=self.full_shape_count, width=10, font=("Segoe UI", 12)).pack(side=LEFT, padx=8)

        export_box = ttk.LabelFrame(left, text=tr(self.lang, "full_shape_export_title"))
        self.translated.append((export_box, "full_shape_export_title", "text"))
        export_box.pack(fill=X, pady=(0, 10))
        self._label(export_box, "full_shape_export_hint", anchor="w", justify=LEFT, wraplength=560).pack(fill=X, padx=10, pady=(8, 4))
        export_actions = Frame(export_box)
        export_actions.pack(fill=X, padx=10, pady=(4, 10))
        self._button(export_actions, "full_shape_export_button", self.start_full_shape_export, font=("Segoe UI", 12, "bold"), height=2).pack(side=LEFT, fill=X, expand=True)
        self._button(export_actions, "full_shape_open_folder", self.open_full_shape_folder, height=2).pack(side=LEFT, padx=(8, 0))

        self._label(right, "full_shape_notes_title", anchor="w", font=("Segoe UI", 12, "bold")).pack(fill=X)
        notes = Text(right, wrap="word", height=26)
        notes.pack(fill=BOTH, expand=True, pady=6)
        notes.insert(END, tr(self.lang, "full_shape_notes"))
        notes.config(state="disabled")
        self.full_shape_notes = notes

    def _build_tools_tab(self):
        self._build_market_banner(self.tools_tab)
        form = Frame(self.tools_tab)
        form.pack(fill=X, padx=10, pady=10)
        self._field(form, "layer_count", self.layer_count, row=0)
        self._field(form, "snapshot_count", self.snapshot_count, row=1)
        self._field(form, "current_count", self.current_count, row=2)
        self._field(form, "table_address", self.inspect_table_value, row=3)
        runtime_entry = self._field(form, "runtime_folder", self.runtime_folder, row=4)
        runtime_entry.config(state="readonly")
        actions = Frame(self.tools_tab)
        actions.pack(fill=X, padx=10, pady=8)
        self._button(actions, "diagnose", self.start_diagnose).pack(side=LEFT)
        self._button(actions, "auto_locate", self.start_auto_locate).pack(side=LEFT, padx=6)
        self._button(actions, "save_snapshot", self.start_save_snapshot).pack(side=LEFT, padx=6)
        self._button(actions, "compare_snapshot", self.start_compare_snapshot).pack(side=LEFT, padx=6)
        self._button(actions, "inspect_table", self.start_inspect_table).pack(side=LEFT, padx=6)
        self._button(actions, "open_runtime_folder", self.open_runtime_folder).pack(side=LEFT, padx=6)

    def _build_tutorial_tab(self):
        self._build_market_banner(self.tutorial_tab)
        self.tutorial_text = Text(self.tutorial_tab, wrap="word")
        self.tutorial_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self._update_tutorial()

    def _build_log(self):
        self.log = Text(self.root, height=9)
        self.log.pack(side=BOTTOM, fill=BOTH, padx=14, pady=(0, 12))
        row = Frame(self.root)
        row.pack(side=BOTTOM, fill=X, padx=14)
        self._label(row, "logs", anchor="w").pack(side=LEFT)
        self._button(row, "export_logs", self.export_detailed_log).pack(side=RIGHT)
        self.full_shape_report_button = self._button(row, "export_full_shape_report", self.export_full_shape_report, state="disabled")
        self.full_shape_report_button.pack(side=RIGHT, padx=(0, 8))
        self._label(row, "progress", anchor="e").pack(side=LEFT, padx=(18, 4))
        Label(row, textvariable=self.progress_text, anchor="w", fg="#005a9e").pack(side=LEFT, fill=X, expand=True)

    def _field(self, parent, key, variable, row, values=None, readonly=False):
        self._label(parent, key, anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=5)
        if values:
            widget = ttk.Combobox(parent, values=values, textvariable=variable, state="readonly" if readonly else "normal")
        else:
            widget = Entry(parent, textvariable=variable)
        widget.grid(row=row, column=1, sticky="ew", pady=5)
        parent.columnconfigure(1, weight=1)
        return widget

    def _on_language(self, _event=None):
        self.lang = LANGUAGES.get(self.lang_combo.get(), "en")
        for widget, key, option in self.translated:
            try:
                widget.config(**{option: tr(self.lang, key)})
            except Exception:
                pass
        self.tabs.tab(self.generate_tab, text=tr(self.lang, "generate_tab"))
        self.tabs.tab(self.import_tab, text=tr(self.lang, "import_tab"))
        self.tabs.tab(self.export_tab, text=tr(self.lang, "export_tab"))
        self.tabs.tab(self.tutorial_tab, text=tr(self.lang, "tutorial_tab"))
        if self.photo is None:
            self.preview_label.config(text=tr(self.lang, "preview_hint"))
            if hasattr(self, "import_preview_label"):
                self.import_preview_label.config(text=tr(self.lang, "preview_hint"))
        if hasattr(self, "advanced_button"):
            self.advanced_button.config(text=tr(self.lang, "hide_advanced" if self.advanced_visible else "show_advanced"))
        if hasattr(self, "full_shape_notes"):
            self.full_shape_notes.config(state="normal")
            self.full_shape_notes.delete("1.0", END)
            self.full_shape_notes.insert(END, tr(self.lang, "full_shape_notes"))
            self.full_shape_notes.config(state="disabled")
        self._update_tutorial()
        self.status.set(tr(self.lang, "ready"))

    def _update_tutorial(self):
        self.tutorial_text.config(state="normal")
        self.tutorial_text.delete("1.0", END)
        self.tutorial_text.insert(END, tr(self.lang, "tutorial"))
        self.tutorial_text.config(state="disabled")

    def _update_setting_description(self, _event=None):
        item = self._selected_setting()
        self.setting_description.config(text=item["description"] if item else "No settings profiles found.")
        if item and self.use_custom_settings.get() != "1":
            values = item.get("values", {})
            self.custom_stop_at.set(values.get("stopAt", "3000"))
            self.custom_max_resolution.set(values.get("maxResolution", "1200"))
            self.custom_random_samples.set(values.get("randomSamples", "3000"))
            self.custom_mutated_samples.set(values.get("mutatedSamples", "1000"))
            self.custom_save_at.set(values.get("saveAt", values.get("stopAt", "3000")))
            self.custom_preprocess_mode.set(values.get("preprocessMode", "none"))

    def _sync_custom_state(self):
        state = "normal" if self.use_custom_settings.get() == "1" else "disabled"
        for entry in getattr(self, "custom_fields", []):
            entry.config(state=state)
        if state == "disabled":
            self._update_setting_description()

    def _effective_setting(self):
        setting = self._selected_setting()
        if not setting or self.use_custom_settings.get() != "1":
            return setting
        return write_custom_settings(setting, self._custom_values())

    def _custom_values(self):
        custom = {
            "stopAt": self.custom_stop_at.get(),
            "maxResolution": self.custom_max_resolution.get(),
            "randomSamples": self.custom_random_samples.get(),
            "mutatedSamples": self.custom_mutated_samples.get(),
            "saveAt": self.custom_save_at.get(),
            "preprocessMode": self.custom_preprocess_mode.get(),
        }
        if not custom["saveAt"] and custom["stopAt"]:
            custom["saveAt"] = custom["stopAt"]
        return custom

    def save_custom_preset(self):
        setting = self._selected_setting()
        if not setting:
            self.log_line("No quality profile selected.")
            return
        USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = filedialog.asksaveasfilename(
            title=tr(self.lang, "save_custom_preset"),
            initialdir=str(USER_SETTINGS_DIR),
            initialfile=f"user-preset-{timestamp}.ini",
            defaultextension=".ini",
            filetypes=[("INI settings", "*.ini"), ("All files", "*.*")],
        )
        if not output:
            return
        try:
            saved_path = write_user_settings_preset(setting, self._custom_values(), output)
        except OSError as exc:
            self.log_line(f"Failed to save preset: {exc}")
            return
        self._reload_settings(preferred_path=saved_path)
        self.log_line(tr(self.lang, "saved_preset").format(path=saved_path))

    def toggle_advanced(self):
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced_frame.pack(fill=X, pady=(0, 10))
        else:
            self.advanced_frame.pack_forget()
        self.advanced_button.config(text=tr(self.lang, "hide_advanced" if self.advanced_visible else "show_advanced"))

    def _selected_setting(self):
        label = self.selected_profile.get()
        for item in self.settings:
            if item["label"] == label:
                return item
        return self.settings[0] if self.settings else None

    def _reload_settings(self, preferred_path=None):
        previous = preferred_path
        if previous is None:
            current = self._selected_setting()
            previous = current.get("path") if current else None
        try:
            previous_resolved = Path(previous).resolve() if previous else None
        except OSError:
            previous_resolved = None
        self.settings = load_settings()
        values = [item["label"] for item in self.settings]
        if hasattr(self, "profile_combo"):
            self.profile_combo["values"] = values
        selected = None
        if previous_resolved:
            for item in self.settings:
                try:
                    if item["path"].resolve() == previous_resolved:
                        selected = item["label"]
                        break
                except OSError:
                    pass
        if selected is None and values:
            selected = values[min(2, len(values) - 1)]
        self.selected_profile.set(selected or "")
        self._update_setting_description()

    def _render_lists(self):
        self.image_list.delete(0, END)
        for path in self.images:
            self.image_list.insert(END, str(path))
        self.json_list.delete(0, END)
        for path in self.json_files:
            self.json_list.insert(END, str(path))

    def _add_json_paths(self, paths):
        added = 0
        for output in best_geometry_jsons(paths):
            output = Path(output)
            if output not in self.outputs:
                self.outputs.append(output)
            if output not in self.json_files:
                self.json_files.append(output)
                added += 1
        return added

    def _load_existing_checkpoints_for_image(self, image_path, log_to_queue=False):
        existing = best_geometry_jsons(generated_jsons(image_path))
        if not existing:
            return 0
        added = self._add_json_paths(existing[:1])
        if added:
            message = tr(self.lang, "existing_checkpoints_found").format(image=Path(image_path).name, count=len(existing))
            if log_to_queue:
                self.queue.put(("log", message))
            else:
                self.log_line(message)
        return added

    def _queue_generated_outputs(self, image_path, before):
        after = generated_jsons(image_path)
        new_outputs = best_geometry_jsons([path for path in after if path.resolve() not in before])
        if not new_outputs and after:
            new_outputs = best_geometry_jsons(after[:1])
        for output in new_outputs:
            if output not in self.outputs:
                self.outputs.append(output)
            if output not in self.json_files:
                self.json_files.append(output)
            self.queue.put(("log", f"Generated: {output}"))
        return new_outputs

    def log_line(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._record_detail(f"UI: {message}")
        self.log.insert(END, f"[{timestamp}] {message}\n")
        self.log.see(END)

    def _record_detail(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        text = str(message).rstrip()
        entry = f"[{timestamp}] {text}"
        with self.detailed_log_lock:
            self.detailed_log_lines.append(entry)
            self.detailed_log_chars += len(entry) + 1
            while self.detailed_log_chars > DETAILED_LOG_MEMORY_LIMIT and self.detailed_log_lines:
                removed = self.detailed_log_lines.popleft()
                self.detailed_log_chars -= len(removed) + 1

    def _format_command(self, cmd):
        return subprocess.list2cmdline([str(item) for item in cmd])

    def _diagnostic_log_header(self):
        try:
            profile = self._selected_setting()
            profile_name = profile["label"] if profile else ""
            profile_path = str(profile["path"]) if profile else ""
        except Exception:
            profile_name = ""
            profile_path = ""
        selected_pid = self.selected_pid_value()
        generator_exists = GENERATOR_EXE.exists()
        lines = [
            f"{APP_DISPLAY_NAME} detailed log",
            f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
            f"App version: {__version__}",
            f"Python: {sys.version.replace(os.linesep, ' ')}",
            f"Platform: {platform.platform()}",
            f"Root: {ROOT}",
            f"Generator: {GENERATOR_EXE} exists={generator_exists}",
            f"Selected game: {self.selected_game.get()}",
            f"Selected PID: {selected_pid}",
            f"Selected process label: {self.selected_pid.get()}",
            f"Template layer count: {self.layer_count.get()}",
            f"Manual count address: {self.count_address.get()}",
            f"Manual table address: {self.table_address.get()}",
            f"Quality profile: {profile_name}",
            f"Quality profile path: {profile_path}",
            f"Custom settings enabled: {self.use_custom_settings.get()}",
            f"Images: {len(self.images)}",
            *[f"  image: {path}" for path in self.images],
            f"JSON files: {len(self.json_files)}",
            *[f"  json: {path}" for path in self.json_files],
            f"Generated outputs: {len(self.outputs)}",
            *[f"  output: {path}" for path in self.outputs],
        ]
        if SESSION_PATH.exists():
            try:
                session_text = SESSION_PATH.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                session_text = f"<failed to read session: {exc}>"
            lines.extend(["Current FH6 session file:", session_text[:4000]])
        return "\n".join(lines).rstrip() + "\n"

    def _build_detailed_log_text(self):
        header = self._diagnostic_log_header()
        try:
            visible_log = self.log.get("1.0", END).strip()
        except Exception:
            visible_log = ""
        with self.detailed_log_lock:
            detail_log = "\n".join(self.detailed_log_lines).strip()
        body = "\n\n".join(
            section
            for section in (
                "=== Detailed Event Log ===\n" + (detail_log or "<empty>"),
                "=== Visible UI Log ===\n" + (visible_log or "<empty>"),
            )
            if section
        )
        marker = f"\n\n--- Log truncated to last {DETAILED_LOG_OUTPUT_LIMIT} characters ---\n"
        prefix = header + "\n"
        budget = DETAILED_LOG_OUTPUT_LIMIT - len(prefix)
        if budget <= len(marker):
            result = (prefix + body)[-DETAILED_LOG_OUTPUT_LIMIT:]
            return result if len(result) <= DETAILED_LOG_OUTPUT_LIMIT else result[-DETAILED_LOG_OUTPUT_LIMIT:]
        if len(body) > budget:
            body = marker + body[-(budget - len(marker)):]
        result = (prefix + body).rstrip()
        if len(result) >= DETAILED_LOG_OUTPUT_LIMIT:
            result = result[:DETAILED_LOG_OUTPUT_LIMIT - 1]
        return result + "\n"

    def export_detailed_log(self):
        initial = f"forza-painter-fh6-log-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        output = filedialog.asksaveasfilename(
            title="Export detailed log",
            defaultextension=".txt",
            initialfile=initial,
            filetypes=[("Text log", "*.txt"), ("All files", "*.*")],
        )
        if not output:
            return
        text = self._build_detailed_log_text()
        try:
            Path(output).write_text(text, encoding="utf-8")
        except OSError as exc:
            self.log_line(f"Failed to export detailed log: {exc}")
            return
        self.log_line(f"Detailed log exported: {output} ({len(text)} chars, limit {DETAILED_LOG_OUTPUT_LIMIT}).")

    def export_full_shape_report(self):
        report_dir_text = str(self.full_shape_last_report_dir.get() or "").strip()
        if not report_dir_text:
            self.log_line(tr(self.lang, "full_shape_no_report"))
            return
        report_dir = Path(report_dir_text)
        if not report_dir.exists() or not report_dir.is_dir():
            self.log_line(tr(self.lang, "full_shape_no_report"))
            return
        initial = f"forza-painter-fh6-full-shape-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        output = filedialog.asksaveasfilename(
            title=tr(self.lang, "export_full_shape_report"),
            defaultextension=".zip",
            initialfile=initial,
            filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
        )
        if not output:
            return
        output_path = Path(output)
        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(report_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(report_dir))
        except OSError as exc:
            self.log_line(f"{tr(self.lang, 'full_shape_report_export_failed')}: {exc}")
            return
        self.log_line(tr(self.lang, "full_shape_report_exported").format(path=output_path))

    def show_full_shape_failure_prompt(self, detail):
        message = tr(self.lang, "full_shape_failure_prompt").format(detail=detail)
        try:
            messagebox.showwarning(tr(self.lang, "full_shape_failed"), message)
        except Exception:
            self.log_line(message)

    def start_update_check(self):
        if self.closed or self.update_check_started:
            return
        self.update_check_started = True
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        try:
            version_source = fetch_text_url(UPDATE_VERSION_URL)
            latest_version = parse_version_source(version_source)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            self.queue.put(("update_failed", str(exc)))
            return

        changelog = ""
        try:
            changelog = fetch_text_url(UPDATE_CHANGELOG_URL)
        except (OSError, urllib.error.URLError) as exc:
            self._record_detail(f"Update changelog fetch failed: {exc}")

        payload = {
            "current": __version__,
            "latest": latest_version,
            "changelog": extract_changelog_section(changelog, latest_version),
        }
        if version_key(latest_version) > version_key(__version__):
            self.queue.put(("update_available", payload))
        else:
            self.queue.put(("update_current", payload))

    def _set_update_indicator(self, text="", color=Theme.WARN):
        if hasattr(self, "update_indicator"):
            self.update_indicator.config(text=text, fg=color)

    def _handle_update_failed(self, error):
        self.update_state = {"status": "failed", "error": error}
        self._set_update_indicator("!", Theme.WARN)
        self.log_line(f"Update check failed: {error}")

    def _handle_update_current(self, payload):
        self.update_state = {"status": "current", **payload}
        self._set_update_indicator("")
        self._record_detail(f"Update check OK: latest={payload.get('latest')}")

    def _handle_update_available(self, payload):
        self.update_state = {"status": "available", **payload}
        self._set_update_indicator("!", Theme.ACCENT)
        self.log_line(f"New version available: v{payload.get('latest')} (current v{__version__})")
        self.show_update_dialog(payload)

    def show_update_status(self, _event=None):
        status = self.update_state.get("status")
        if status == "failed":
            messagebox.showwarning(
                tr(self.lang, "update_check_failed_title"),
                tr(self.lang, "update_check_failed_message").format(error=self.update_state.get("error", "")),
                parent=self.root,
            )
        elif status == "available":
            self.show_update_dialog(self.update_state)

    def show_update_dialog(self, payload=None):
        payload = payload or self.update_state
        if self.update_dialog is not None and self.update_dialog.winfo_exists():
            self.update_dialog.lift()
            self.update_dialog.focus_force()
            return

        latest = payload.get("latest", "")
        changelog = payload.get("changelog") or "No changelog section was available."
        dialog = Toplevel(self.root)
        self.update_dialog = dialog
        dialog.title(tr(self.lang, "update_available_title"))
        dialog.configure(bg=Theme.BG)
        dialog.resizable(True, True)

        body = Frame(dialog, bg=Theme.BG)
        body.pack(fill=BOTH, expand=True, padx=16, pady=14)
        Label(
            body,
            text=tr(self.lang, "update_available_message").format(current=__version__, latest=latest),
            bg=Theme.BG,
            fg=Theme.TEXT,
            justify=LEFT,
            anchor="w",
            font=("Segoe UI", 11, "bold"),
        ).pack(fill=X, pady=(0, 10))
        Label(
            body,
            text=tr(self.lang, "changelog"),
            bg=Theme.BG,
            fg=Theme.MUTED,
            anchor="w",
        ).pack(fill=X)

        text_frame = Frame(body, bg=Theme.BG)
        text_frame.pack(fill=BOTH, expand=True, pady=(4, 12))
        changelog_text = Text(text_frame, width=80, height=18, wrap="word")
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=changelog_text.yview)
        changelog_text.configure(
            yscrollcommand=scrollbar.set,
            bg=Theme.INPUT,
            fg=Theme.TEXT,
            insertbackground=Theme.TEXT,
            selectbackground=Theme.ACCENT_DARK,
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            relief="flat",
        )
        changelog_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill="y")
        changelog_text.insert(END, changelog)
        changelog_text.config(state="disabled")

        actions = Frame(body, bg=Theme.BG)
        actions.pack(fill=X)

        def close_update_dialog():
            self.update_dialog = None
            dialog.destroy()

        def open_update_page():
            webbrowser.open(UPDATE_RELEASE_URL)
            close_update_dialog()

        Button(
            actions,
            text=tr(self.lang, "update_later"),
            command=close_update_dialog,
            bg=Theme.BUTTON,
            fg=Theme.TEXT,
            activebackground=Theme.BUTTON_ACTIVE,
            activeforeground=Theme.TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
        ).pack(side=RIGHT)
        Button(
            actions,
            text=tr(self.lang, "update_open_page"),
            command=open_update_page,
            bg=Theme.ACCENT_DARK,
            fg="#ffffff",
            activebackground=Theme.ACCENT,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
        ).pack(side=RIGHT, padx=(0, 8))

        dialog.protocol("WM_DELETE_WINDOW", close_update_dialog)

    def _reset_generation_eta(self):
        self.eta_samples.clear()
        self.eta_display_time = None
        self.eta_smoothed_seconds_per_layer = None
        self.eta_display_remaining = None
        self.eta_max_layer_seen = None
        self.eta_recycle_notice_active = False

    def _format_remaining_time(self, seconds):
        seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        suffix = {"zh": "剩余", "zh-tw": "剩餘", "ko": "남음"}.get(self.lang, "left")
        if hours:
            return f"{hours}h {minutes:02d}m {suffix}"
        if minutes:
            return f"{minutes}m {seconds:02d}s {suffix}"
        return f"{seconds}s {suffix}"

    def _progress_with_eta(self, friendly):
        match = re.match(r"Generated layer\s+(\d+)/(\d+)", friendly)
        if not match:
            return friendly
        current = int(match.group(1))
        total = int(match.group(2))
        now = time.time()
        if self.eta_max_layer_seen is not None and current <= self.eta_max_layer_seen:
            if current < self.eta_max_layer_seen and not self.eta_recycle_notice_active:
                self.eta_recycle_notice_active = True
                return tr(self.lang, "generator_recycled_layers").format(max_layer=self.eta_max_layer_seen, total=total)
            return None
        self.eta_max_layer_seen = current
        self.eta_recycle_notice_active = False
        self.eta_samples.append((current, now))
        while len(self.eta_samples) > 1 and now - self.eta_samples[0][1] > ETA_MAX_HISTORY_SECONDS:
            self.eta_samples.popleft()

        remaining_layers = max(0, total - current)
        if remaining_layers == 0:
            self.eta_display_remaining = 0
            self.eta_display_time = now
            eta_time = datetime.fromtimestamp(now).strftime("%H:%M:%S")
            return f"{friendly} | ETA {eta_time} ({self._format_remaining_time(0)})"

        if len(self.eta_samples) < 2:
            return friendly

        start_layer, start_time = self.eta_samples[0]
        for sample_layer, sample_time in self.eta_samples:
            if now - sample_time <= ETA_WINDOW_SECONDS:
                start_layer, start_time = sample_layer, sample_time
                break
        layer_delta = current - start_layer
        elapsed_seconds = now - start_time
        if layer_delta < ETA_MIN_WINDOW_LAYERS or elapsed_seconds < ETA_MIN_WINDOW_SECONDS:
            start_layer, start_time = self.eta_samples[0]
            layer_delta = current - start_layer
            elapsed_seconds = now - start_time
            if layer_delta < ETA_MIN_WINDOW_LAYERS or elapsed_seconds < ETA_MIN_WINDOW_SECONDS:
                return friendly

        seconds_per_layer = elapsed_seconds / layer_delta
        self.eta_smoothed_seconds_per_layer = seconds_per_layer
        measured_remaining = seconds_per_layer * remaining_layers
        if self.eta_display_remaining is None:
            self.eta_display_remaining = measured_remaining
        else:
            elapsed_since_display = now - self.eta_display_time if self.eta_display_time is not None else 0
            expected_remaining = max(0, self.eta_display_remaining - elapsed_since_display)
            if measured_remaining < expected_remaining * 0.65 or measured_remaining > expected_remaining * 1.6:
                self.eta_display_remaining = measured_remaining
            else:
                self.eta_display_remaining = expected_remaining * 0.35 + measured_remaining * 0.65
        self.eta_display_time = now
        remaining_seconds = self.eta_display_remaining
        eta_time = datetime.fromtimestamp(now + remaining_seconds).strftime("%H:%M:%S")
        return f"{friendly} | ETA {eta_time} ({self._format_remaining_time(remaining_seconds)})"

    def friendly_generator_line(self, line):
        text = (line or "").strip()
        if not text:
            return None
        progress = re.match(r"\[(\d+)/(\d+)\]\s+(.*)", text)
        if progress:
            current, total, detail = progress.groups()
            if "Added rotated ellipse" in detail:
                return f"Generated layer {current}/{total}"
            if "Saved geometry checkpoint" in detail:
                return f"Saved JSON checkpoint {current}/{total}"
            if "Saved preview snapshot" in detail:
                return f"Updated preview {current}/{total}"
            if "Step completed" in detail:
                return None
            return None
        if text.startswith("Loaded image:"):
            return text
        if text.startswith("Settings:"):
            return text
        if text.startswith("OpenCL: Selected device"):
            return text
        if text.startswith("Scoring mode:"):
            return text
        if text in ("FINISHED",):
            return text
        if "error" in text.lower() or "failed" in text.lower() or "panic" in text.lower():
            return text
        return None

    def queue_generator_message(self, friendly, last_message):
        if not friendly or friendly == last_message:
            return last_message
        if friendly.startswith("Generated layer "):
            message = self._progress_with_eta(friendly)
            if not message:
                return last_message
            self.queue.put(("progress", message))
            self.queue.put(("log", message))
            return friendly
        if friendly == "FINISHED":
            self.queue.put(("progress", friendly))
        self.queue.put(("log", friendly))
        return friendly

    def _int_setting(self, setting, key, default=0):
        try:
            return int(str(setting.get("values", {}).get(key, default)).strip())
        except (TypeError, ValueError):
            return default

    def _log_generation_load_warning(self, setting):
        stop_at = self._int_setting(setting, "stopAt")
        random_samples = self._int_setting(setting, "randomSamples")
        mutated_samples = self._int_setting(setting, "mutatedSamples")
        max_resolution = self._int_setting(setting, "maxResolution")
        if random_samples >= 200000 or mutated_samples >= 8000 or max_resolution >= 2000:
            self.queue.put((
                "log",
                "High quality generation selected: "
                f"layers={stop_at}, randomSamples={random_samples}, "
                f"mutatedSamples={mutated_samples}, maxResolution={max_resolution}. "
                "The first layer can take a long time before progress appears.",
            ))

    def _generator_exit_message(self, returncode):
        if returncode in (3221225477, -1073741819):
            return (
                "GPU generator crashed with Windows access violation 0xC0000005. "
                "This is usually an OpenCL/GPU driver or generator runtime crash, not an import error. "
                "Try a lower preset, lower Max resolution / Random samples, update the GPU driver, "
                "or convert the source image to a normal PNG/JPG path and retry."
            )
        if returncode == 3221226505:
            return (
                "GPU generator crashed with Windows stack buffer overrun 0xC0000409. "
                "Try updating the GPU driver, lowering the preset, or converting the image to PNG/JPG."
            )
        return f"Generator exited with code {returncode}."

    def add_images(self):
        files = filedialog.askopenfilenames(
            title="Choose images",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")],
        )
        added_paths = []
        for item in files:
            path = Path(item)
            if path.exists() and path not in self.images:
                self.images.append(path)
                added_paths.append(path)
                self._load_existing_checkpoints_for_image(path)
        self._render_lists()
        if files:
            self.show_source_preview(Path(files[0]))
        if added_paths:
            existing_added = sum(1 for path in added_paths if generated_jsons(path))
            if existing_added:
                self.log_line(tr(self.lang, "cannot_resume_checkpoint"))

    def remove_selected_image(self):
        selection = list(self.image_list.curselection())
        if not selection:
            self.log_line(tr(self.lang, "no_image_selected"))
            return
        for index in sorted(selection, reverse=True):
            try:
                del self.images[index]
            except IndexError:
                pass
        self._render_lists()
        self.current_preview_request = None
        self.preview_label.config(image="", text=tr(self.lang, "preview_hint"))
        self.preview_label.image = None

    def _unique_preset_destination(self, source_path):
        USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        stem = source_path.stem
        suffix = source_path.suffix or ".ini"
        candidate = USER_SETTINGS_DIR / f"{stem}{suffix}"
        index = 2
        while candidate.exists():
            candidate = USER_SETTINGS_DIR / f"{stem} ({index}){suffix}"
            index += 1
        return candidate

    def import_preset(self):
        files = filedialog.askopenfilenames(
            title="Import generator preset",
            filetypes=[("INI settings", "*.ini"), ("All files", "*.*")],
        )
        imported = []
        for item in files:
            source = Path(item)
            if not source.exists():
                continue
            destination = self._unique_preset_destination(source)
            try:
                shutil.copy2(source, destination)
                imported.append(destination)
            except OSError as exc:
                self.log_line(f"Failed to import preset {source}: {exc}")
        if imported:
            self._reload_settings(preferred_path=imported[-1])
            self.log_line(tr(self.lang, "imported_presets").format(count=len(imported)))

    def open_preset_folder(self):
        USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(USER_SETTINGS_DIR)

    def add_json(self):
        files = filedialog.askopenfilenames(
            title="Choose geometry JSON",
            filetypes=[("Geometry JSON", "*.json"), ("All files", "*.*")],
        )
        for item in files:
            path = Path(item)
            if path.exists() and path not in self.json_files:
                self.json_files.append(path)
        self._render_lists()
        if files:
            self.show_json_preview(Path(files[0]))

    def remove_selected_json(self):
        selection = list(self.json_list.curselection())
        if not selection:
            self.log_line(tr(self.lang, "no_json_selected"))
            return
        for index in sorted(selection, reverse=True):
            try:
                del self.json_files[index]
            except IndexError:
                pass
        self._render_lists()
        self.current_preview_request = None
        if hasattr(self, "import_preview_label"):
            self.import_preview_label.config(image="", text=tr(self.lang, "preview_hint"))
            self.import_preview_label.image = None

    def use_generated_outputs(self):
        for path in self.outputs:
            if path.exists() and path not in self.json_files:
                self.json_files.append(path)
        self._render_lists()
        self.log_line(f"Added {len(self.outputs)} generated JSON file(s) to import list.")

    def _preview_selected_image(self, _event=None):
        selection = self.image_list.curselection()
        if selection:
            self.show_source_preview(self.images[selection[0]])

    def _preview_selected_json(self, _event=None):
        selection = self.json_list.curselection()
        if selection:
            self.show_json_preview(self.json_files[selection[0]])

    def _active_preview_label(self):
        if hasattr(self, "tabs") and hasattr(self, "import_preview_label"):
            try:
                if self.tabs.select() == str(self.import_tab):
                    return self.import_preview_label
            except Exception:
                pass
        return getattr(self, "preview_label", None)

    def _preview_labels(self):
        labels = []
        for name in ("preview_label", "import_preview_label"):
            label = getattr(self, name, None)
            if label is not None:
                labels.append(label)
        return labels

    def _preview_bounds(self, label=None):
        label = label or self._active_preview_label()
        if label is None:
            return PREVIEW_MAX, PREVIEW_MAX
        try:
            width = label.winfo_width()
            height = label.winfo_height()
        except Exception:
            width = height = 0
        if width <= 32 or height <= 32:
            return PREVIEW_MAX, PREVIEW_MAX
        return max(1, width - 16), max(1, height - 16)

    def _bucket_preview_bounds(self, bounds):
        try:
            width, height = bounds
            width = int(width)
            height = int(height)
        except (TypeError, ValueError):
            return PREVIEW_MAX, PREVIEW_MAX
        bucket = max(1, PREVIEW_SIZE_BUCKET)
        return (
            max(1, int(round(width / bucket) * bucket)),
            max(1, int(round(height / bucket) * bucket)),
        )

    def _schedule_preview_refresh(self, _event=None, delay=None):
        if not self.current_preview_request or self.closed:
            return
        label = self._active_preview_label()
        event_widget = getattr(_event, "widget", None)
        if event_widget in self._preview_labels():
            if event_widget is not label:
                return
            bounds = self._bucket_preview_bounds((getattr(_event, "width", 0), getattr(_event, "height", 0)))
        else:
            bounds = self._bucket_preview_bounds(self._preview_bounds(label))
        schedule_key = (self.current_preview_request, bounds, id(label) if label is not None else None)
        if schedule_key == self.preview_last_schedule_key:
            return
        self.preview_last_schedule_key = schedule_key
        if self.preview_resize_job is not None:
            try:
                self.root.after_cancel(self.preview_resize_job)
            except Exception:
                pass
        if delay is None:
            delay = PREVIEW_RESIZE_DEBOUNCE_MS
        self.preview_resize_job = self.root.after(max(1, int(delay)), self._refresh_current_preview)

    def _preview_cache_key(self, request, bounds):
        kind, path_text = request
        path = Path(path_text)
        try:
            stat = path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            stamp = (0, 0)
        return kind, str(path), stamp, bounds

    def _remember_preview_cache(self, key, data):
        if not data:
            return
        self.preview_cache[key] = data
        while len(self.preview_cache) > PREVIEW_CACHE_LIMIT:
            self.preview_cache.pop(next(iter(self.preview_cache)))

    def _refresh_current_preview(self):
        self.preview_resize_job = None
        request = self.current_preview_request
        if not request or self.closed:
            return
        kind, path = request
        path = Path(path)
        if not path.exists():
            return
        bounds = self._bucket_preview_bounds(self._preview_bounds())
        cache_key = self._preview_cache_key(request, bounds)
        cached = self.preview_cache.get(cache_key)
        if cached:
            display_key = (cache_key, id(self._active_preview_label()))
            if display_key == self.preview_display_cache_key:
                return
            self.preview_display_cache_key = display_key
            self.show_preview(cached)
            return
        self.preview_render_token += 1
        token = self.preview_render_token
        threading.Thread(target=self._preview_render_worker, args=(token, request, bounds, cache_key), daemon=True).start()

    def _preview_render_worker(self, token, request, bounds, cache_key):
        kind, path = request
        path = Path(path)
        if kind == "json":
            data = render_geometry_json(path, bounds)
        else:
            data = render_source_image(path, bounds)
        self.queue.put(("preview_rendered", (token, request, cache_key, data)))

    def show_json_preview(self, path):
        path = Path(path)
        self.current_preview_request = ("json", str(path))
        self.preview_last_schedule_key = None
        self._schedule_preview_refresh(delay=PREVIEW_RENDER_START_MS)

    def show_preview(self, data):
        label = self._active_preview_label()
        if not data:
            self.current_preview_request = None
            self.preview_last_schedule_key = None
            self.preview_display_cache_key = None
            message = tr(self.lang, "preview_unavailable")
            if label is not None:
                label.config(image="", text=message, bg="#202020")
                label.image = None
            return
        self.photo = data
        image = PhotoImage(data=data)
        if label is not None:
            label.config(image=image, text="", bg="#202020")
            label.image = image

    def show_source_preview(self, path):
        path = Path(path)
        self.current_preview_request = ("source", str(path))
        self.preview_last_schedule_key = None
        self._schedule_preview_refresh(delay=PREVIEW_RENDER_START_MS)

    def show_preview_file(self, path, remember=True):
        path = Path(path)
        if remember:
            self.current_preview_request = ("file", str(path))
            self.preview_last_schedule_key = None
        self._schedule_preview_refresh(delay=PREVIEW_RENDER_START_MS)

    def refresh_processes(self):
        self.processes = game_processes()
        values = [item["label"] for item in self.processes]
        if not values:
            values = [tr(self.lang, "no_game")]
        self.process_combo["values"] = values
        if self.processes:
            self.selected_pid.set(values[0])
            self.selected_game.set(self.processes[0]["profile"])
        else:
            self.selected_pid.set("")

    def selected_pid_value(self):
        raw = self.selected_pid.get()
        match = re.search(r"pid\s+(\d+)", raw, re.I)
        if match:
            return int(match.group(1))
        try:
            return int(raw.strip())
        except ValueError:
            return None

    def _pid_matches_game(self, pid, game):
        profile = PROFILES.get(game)
        if not pid or not profile:
            return False
        try:
            process_name = psutil.Process(pid).name().lower()
        except psutil.Error:
            return False
        return process_name in [name.lower() for name in profile.process_names]

    def ensure_live_game_pid(self):
        game = self.selected_game.get() or "fh6"
        pid = self.selected_pid_value()
        if self._pid_matches_game(pid, game):
            return pid
        if pid:
            self.log_line(f"Selected game process pid {pid} is no longer running; refreshing process list.")
        self.refresh_processes()
        game = self.selected_game.get() or game
        pid = self.selected_pid_value()
        if self._pid_matches_game(pid, game):
            return pid
        self.log_line("No live supported game process is selected. Start FH6, then click Refresh.")
        return None

    def stop_generate(self):
        with self.generation_lock:
            if not self.generation_running:
                self.log_line(tr(self.lang, "no_generation_running"))
                return
            proc = self.current_generator_proc
        self.log_line(tr(self.lang, "stopping_generation"))
        self.shutdown_event.set()
        if proc is not None:
            self._terminate_process(proc)
        self.status.set(tr(self.lang, "stopped"))

    def start_generate(self):
        with self.generation_lock:
            if self.generation_running:
                self.log_line("Generation is already running. Wait for it to finish or use Stop current generation.")
                return
            self.generation_running = True
        if not self.images:
            with self.generation_lock:
                self.generation_running = False
            self.log_line("No images selected.")
            return
        setting = self._effective_setting()
        if not setting:
            with self.generation_lock:
                self.generation_running = False
            self.log_line("No quality profile selected.")
            return
        if not GENERATOR_EXE.exists():
            with self.generation_lock:
                self.generation_running = False
            self.log_line(f"Missing generator: {GENERATOR_EXE}")
            return
        self.shutdown_event.clear()
        self._reset_generation_eta()
        self.progress_text.set("")
        self.status.set(tr(self.lang, "running"))
        if hasattr(self, "generate_button"):
            self.generate_button.config(state="disabled")
        if hasattr(self, "stop_generate_button"):
            self.stop_generate_button.config(state="normal")
        threading.Thread(target=self._generate_worker, args=(setting,), daemon=True).start()

    def _generate_worker(self, setting):
        try:
            self.queue.put(("log", f"Selected profile: {setting['path'].name}"))
            self._log_generation_load_warning(setting)
            for image_path in list(self.images):
                if self.shutdown_event.is_set():
                    self.queue.put(("status", tr(self.lang, "stopped")))
                    return
                self._reset_generation_eta()
                input_image = preprocess_input_image(image_path, setting)
                if input_image != image_path:
                    self.queue.put(("log", f"Preprocessed image: {input_image}"))
                before = {path.resolve() for path in generated_jsons(input_image)}
                preview_path = generator_preview_path(input_image)
                if preview_path.exists():
                    try:
                        preview_path.unlink()
                    except OSError:
                        pass
                self.queue.put(("log", f"Generating: {image_path}"))
                self.queue.put(("preview_file", image_path))
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                cmd = build_generator_command(input_image, setting)
                self._record_detail(f"GENERATOR COMMAND: {self._format_command(cmd)}")
                self.queue.put(("log", f"Running GPU generator with {setting['path'].name}"))
                if self.shutdown_event.is_set():
                    self.queue.put(("status", tr(self.lang, "stopped")))
                    return
                proc = self._popen_registered(
                    cmd,
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=flags,
                    env=build_generator_env(),
                )
                if proc is None:
                    self.queue.put(("status", tr(self.lang, "stopped")))
                    return
                with self.generation_lock:
                    self.current_generator_proc = proc

                last_preview = None
                last_preview_mtime = None
                last_generator_message = None
                output_queue = queue.Queue()

                def _read_generator_output():
                    try:
                        for raw_line in proc.stdout:
                            self._record_detail(f"GENERATOR RAW: {raw_line.rstrip()}")
                            output_queue.put(raw_line)
                    finally:
                        output_queue.put(None)

                reader = threading.Thread(target=_read_generator_output, daemon=True)
                reader.start()

                def _drain_generator_output():
                    nonlocal last_generator_message
                    while True:
                        try:
                            raw_line = output_queue.get_nowait()
                        except queue.Empty:
                            break
                        if raw_line is None:
                            continue
                        friendly = self.friendly_generator_line(raw_line)
                        last_generator_message = self.queue_generator_message(friendly, last_generator_message)

                next_preview_scan = 0.0
                next_json_scan = 0.0

                try:
                    while proc.poll() is None:
                        if self.shutdown_event.is_set():
                            self._terminate_process(proc)
                            outputs = self._queue_generated_outputs(input_image, before)
                            for output in outputs:
                                self.queue.put(("log", tr(self.lang, "checkpoint_available_after_failure").format(path=output)))
                            if outputs:
                                self.queue.put(("render_lists", None))
                            self.queue.put(("status", tr(self.lang, "stopped")))
                            return
                        _drain_generator_output()
                        now = time.monotonic()
                        if now >= next_preview_scan:
                            next_preview_scan = now + GENERATOR_PREVIEW_SCAN_SECONDS
                            preview_files = generated_preview_files(input_image)
                            if preview_files:
                                newest_preview = preview_files[0]
                                preview_mtime = newest_preview.stat().st_mtime
                                if preview_mtime != last_preview_mtime:
                                    last_preview_mtime = preview_mtime
                                    self.queue.put(("preview_file", newest_preview))
                        if now >= next_json_scan:
                            next_json_scan = now + GENERATOR_JSON_SCAN_SECONDS
                            newest = generated_jsons(input_image)
                            if newest and newest[0] != last_preview:
                                last_preview = newest[0]
                        time.sleep(GENERATOR_POLL_SLEEP_SECONDS)
                    if self.shutdown_event.is_set():
                        return
                    reader.join(timeout=1)
                    _drain_generator_output()
                finally:
                    self._unregister_process(proc)
                    with self.generation_lock:
                        if self.current_generator_proc is proc:
                            self.current_generator_proc = None
                if proc.returncode != 0:
                    self._record_detail(f"GENERATOR EXIT: {proc.returncode}")
                    outputs = self._queue_generated_outputs(input_image, before)
                    for output in outputs:
                        self.queue.put(("log", tr(self.lang, "checkpoint_available_after_failure").format(path=output)))
                    if outputs:
                        self.queue.put(("render_lists", None))
                    self.queue.put(("log", self._generator_exit_message(proc.returncode)))
                    self.queue.put(("status", tr(self.lang, "failed")))
                    return
                self._record_detail("GENERATOR EXIT: 0")
                new_outputs = self._queue_generated_outputs(input_image, before)
                if not new_outputs:
                    self.queue.put(("log", "Generator finished but no JSON output was found."))
                    self.queue.put(("status", tr(self.lang, "failed")))
                    return
                for output in new_outputs:
                    preview_files = generated_preview_files(input_image)
                    if preview_files:
                        self.queue.put(("preview_file", preview_files[0]))
                    else:
                        self.queue.put(("preview_json", output))
            self.queue.put(("render_lists", None))
            self.queue.put(("status", tr(self.lang, "done")))
        except Exception as exc:
            self.queue.put(("log", f"Generator failed: {exc}"))
            self.queue.put(("status", tr(self.lang, "failed")))
        finally:
            self.queue.put(("generation_done", None))

    def open_output_folder(self):
        folder = None
        if self.outputs:
            folder = self.outputs[-1].parent
        elif self.images:
            folder = self.images[-1].parent
        if folder and folder.exists():
            os.startfile(folder)

    def open_runtime_folder(self):
        ROOT.mkdir(parents=True, exist_ok=True)
        os.startfile(ROOT)

    def run_subprocess(self, cmd, timeout=None):
        self._record_detail(f"HELPER COMMAND: {self._format_command(cmd)}")
        self.queue.put(("log", self._friendly_command_name(cmd)))
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        env = os.environ.copy()
        env.update({"FORZA_PAINTER_NO_ELEVATE": "1", "FORZA_PAINTER_NO_PAUSE": "1"})
        if self.shutdown_event.is_set():
            self._record_detail("HELPER EXIT: 130 before start")
            return 130
        proc = self._popen_registered(
            [str(x) for x in cmd],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            env=env,
        )
        if proc is None:
            self._record_detail("HELPER EXIT: 130 no process")
            return 130
        started = time.time()
        try:
            while True:
                if self.shutdown_event.is_set():
                    self._terminate_process(proc)
                    self._record_detail("HELPER EXIT: 130 stopped")
                    return 130
                line = proc.stdout.readline()
                if line:
                    self._record_detail(f"HELPER RAW: {line.rstrip()}")
                    friendly = self._friendly_subprocess_line(line.rstrip())
                    if friendly:
                        self.queue.put(("log", friendly))
                if proc.poll() is not None:
                    break
                if timeout and time.time() - started > timeout:
                    self._terminate_process(proc)
                    self._record_detail(f"HELPER EXIT: 124 timeout after {timeout} seconds")
                    self.queue.put(("log", f"Timed out after {timeout} seconds."))
                    return 124
                time.sleep(0.05)
            if self.shutdown_event.is_set():
                self._record_detail("HELPER EXIT: 130 stopped after process exit")
                return 130
            for line in proc.stdout.read().splitlines():
                self._record_detail(f"HELPER RAW: {line.rstrip()}")
                friendly = self._friendly_subprocess_line(line.rstrip())
                if friendly:
                    self.queue.put(("log", friendly))
            self._record_detail(f"HELPER EXIT: {proc.returncode}")
            return proc.returncode
        finally:
            self._unregister_process(proc)

    def _friendly_command_name(self, cmd):
        joined = " ".join(str(x) for x in cmd)
        if "fh6_probe.py" in joined and "--auto-locate" in joined:
            return tr(self.lang, "locating")
        if "fh6_typecode_probe" in joined:
            return tr(self.lang, "full_shape_locating")
        if "fh6_typecode_import" in joined:
            return tr(self.lang, "full_shape_importing")
        if "fh6_typecode_export" in joined:
            return tr(self.lang, "full_shape_exporting")
        if "fh6_typecode_trim" in joined:
            return tr(self.lang, "full_shape_trimming")
        if "main.py" in joined:
            return tr(self.lang, "importing")
        return "Starting helper..."

    def _check_json_layer_fit(self, json_path, layer_count):
        try:
            from generator_backend import geometry_shape_count
            json_layers = geometry_shape_count(json_path)
            template_layers = int(layer_count)
        except Exception:
            return
        usable_layers = max(0, template_layers - 4)
        if json_layers and template_layers and json_layers > usable_layers:
            self.queue.put(("log", f"{tr(self.lang, 'json_needs_more_template_layers')} JSON={json_layers}, template={template_layers}, usable={usable_layers}"))
        if json_layers and usable_layers and json_layers < usable_layers * 0.75:
            self.queue.put(("log", f"{tr(self.lang, 'json_too_small')} JSON={json_layers}, usable={usable_layers}"))

    def _friendly_subprocess_line(self, line):
        if not line:
            return None
        raw = line.strip()
        lower = raw.lower()
        noisy_parts = (
            "base:",
            "candidate score=",
            "layout candidate",
            "table[",
            "ptr=0x",
            "count=0x",
            "tablefield=",
            "wrote fh6 session location",
            "fh6 layout-count scan checked",
            "process: forzahorizon",
            "current values:",
            "loaded ",
            "descriptor @",
            "info found:",
            "vtp found:",
        )
        if any(part in lower for part in noisy_parts):
            return None
        if "fast fh6 layer group candidates:" in lower:
            return tr(self.lang, "located")
        if "no safe fh6 layer group" in lower:
            return tr(self.lang, "safe_stop")
        if "auto-locating fh6 layer count/table" in lower:
            return tr(self.lang, "locating")
        if "cliverylayer table found" in lower:
            return tr(self.lang, "located")
        if "forza horizon 6 detected" in lower:
            return raw
        if raw.startswith("Writing layer") or raw == "DONE!" or raw.startswith("The ideal background color"):
            return raw
        if "openprocess" in lower or "error" in lower or "failed" in lower or "traceback" in lower:
            return raw
        if raw.startswith("<class 'SystemExit'>") or raw.startswith("SystemExit: 0"):
            return None
        return raw

    def start_auto_locate(self):
        pid = self.ensure_live_game_pid()
        layer_count = self.layer_count.get().strip()
        if not pid or not layer_count:
            self.log_line("PID and template layer count are required.")
            return
        self.status.set(tr(self.lang, "running"))
        threading.Thread(target=self._auto_locate_worker, args=(pid, layer_count), daemon=True).start()

    def _auto_locate_worker(self, pid, layer_count):
        clear_session_location()
        cmd = [
            *helper_command("fh6_probe"),
            "--game",
            self.selected_game.get() or "fh6",
            "--pid",
            str(pid),
            "--layer-count",
            str(layer_count),
            "--auto-locate",
            "--write-session",
            SESSION_PATH,
            "--limit-mb",
            str(MEMORY_SNAPSHOT_LIMIT_MB),
            "--max-matches",
            "500000",
            "--inspect-radius",
            "0x800",
            "--max-seconds",
            str(FH6_AUTO_LOCATE_MAX_SECONDS),
        ]
        self.queue.put(("log", tr(self.lang, "locating_wait")))
        code = self.run_subprocess(cmd, timeout=FH6_AUTO_LOCATE_TIMEOUT_SECONDS)
        located = False
        if code == 0 and SESSION_PATH.exists():
            session = load_session_location()
            if session_matches_current_import(session, self.selected_game.get() or "fh6", pid, layer_count):
                self.queue.put(("log", tr(self.lang, "located")))
                located = True
        self.queue.put(("status", tr(self.lang, "done") if located else tr(self.lang, "failed")))
        return located

    def start_import(self):
        if not self.json_files:
            self.log_line("No JSON files selected.")
            return
        paths = self._json_paths_for_import()
        layer_count = self.layer_count.get().strip()
        if not layer_count:
            self.log_line(tr(self.lang, "layer_count_required"))
            self.layer_count_entry.config(highlightbackground="red", highlightthickness=1)
            return
        self.layer_count_entry.config(highlightbackground=Theme.BORDER, highlightthickness=0)
        pid = self.ensure_live_game_pid()
        if not pid:
            return
        self.status.set(tr(self.lang, "running"))
        threading.Thread(target=self._import_worker, args=(pid, paths), daemon=True).start()

    def _json_paths_for_import(self):
        try:
            selection = self.json_list.curselection()
        except Exception:
            selection = ()
        if selection:
            return [self.json_files[selection[0]]]
        return list(self.json_files)

    def _import_worker(self, pid, paths):
        game = self.selected_game.get() or "fh6"
        count_address = parse_hex_or_empty(self.count_address.get())
        table_address = parse_hex_or_empty(self.table_address.get())
        layer_count = self.layer_count.get().strip()
        typecode_paths = [path for path in paths if is_typecode_json(path)]
        if typecode_paths:
            if game != "fh6":
                self.queue.put(("log", "Full-shape JSON import is only supported for FH6."))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            if len(paths) != 1:
                self.queue.put(("log", tr(self.lang, "full_shape_single_json_required")))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            try:
                template_count = int(layer_count)
                shape_count = typecode_shape_count(typecode_paths[0])
            except Exception as exc:
                self.queue.put(("log", f"{tr(self.lang, 'full_shape_invalid_json')}: {exc}"))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            if shape_count > template_count:
                self.queue.put(("log", f"{tr(self.lang, 'full_shape_too_many_shapes')} JSON={shape_count}, template={template_count}"))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            self._full_shape_import_worker(
                pid,
                template_count,
                shape_count,
                Path(typecode_paths[0]),
                True,
            )
            return
        if not count_address and not table_address and game == "fh6":
            clear_session_location()
            if pid and layer_count:
                self.queue.put(("log", tr(self.lang, "locating")))
                located = self._auto_locate_worker(pid, layer_count)
                session = load_session_location()
                if located and session_matches_current_import(session, game, pid, layer_count):
                    count_address = "0x{:x}".format(int(session["count_address"]))
                    table_address = "0x{:x}".format(int(session["table_address"]))
                else:
                    self.queue.put(("status", tr(self.lang, "failed")))
                    return
        for path in list(paths):
            if game == "fh6" and layer_count:
                self._check_json_layer_fit(path, layer_count)
            cmd = [*helper_command("main"), "--game", game, "--no-preview"]
            if pid:
                cmd.extend(["--pid", str(pid)])
            if count_address:
                cmd.extend(["--layer-count-address", count_address])
            if table_address:
                cmd.extend(["--layer-table-address", table_address])
            if game == "fh6" and layer_count:
                cmd.extend(["--layer-count-value", str(layer_count)])
            cmd.append(path)
            code = self.run_subprocess(cmd)
            if code != 0:
                self.queue.put(("status", tr(self.lang, "failed")))
                return
        self.queue.put(("status", tr(self.lang, "done")))

    def choose_full_shape_json(self):
        path = filedialog.askopenfilename(
            title=tr(self.lang, "full_shape_choose_json"),
            filetypes=[("Full-shape JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        selected = Path(path)
        self.full_shape_json_path.set(str(selected))
        try:
            count = typecode_shape_count(selected)
            self.log_line(f"{tr(self.lang, 'full_shape_selected_json')} {selected.name} ({count} shapes)")
        except Exception as exc:
            self.log_line(f"{tr(self.lang, 'full_shape_invalid_json')}: {exc}")

    def open_full_shape_folder(self):
        folder = Path(self.full_shape_last_output_dir.get() or FULL_SHAPE_ROOT)
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def _full_shape_count_value(self):
        try:
            count = int(str(self.full_shape_count.get()).strip())
        except ValueError:
            self.log_line(tr(self.lang, "full_shape_count_required"))
            return None
        if count <= 0:
            self.log_line(tr(self.lang, "full_shape_count_required"))
            return None
        return count

    def _full_shape_run_dir(self, prefix, name):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(name or "run")).strip("-") or "run"
        run_dir = FULL_SHAPE_ROOT / f"{prefix}-{safe_name}-{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def start_full_shape_import(self):
        pid = self.ensure_live_game_pid()
        if not pid:
            return
        if self.layer_count.get().strip():
            self.full_shape_count.set(self.layer_count.get().strip())
        template_count = self._full_shape_count_value()
        if not template_count:
            return
        json_path = Path(self.full_shape_json_path.get().strip())
        if not json_path.exists():
            self.log_line(tr(self.lang, "full_shape_no_json"))
            return
        try:
            shape_count = typecode_shape_count(json_path)
        except Exception as exc:
            self.log_line(f"{tr(self.lang, 'full_shape_invalid_json')}: {exc}")
            return
        if shape_count <= 0:
            self.log_line(tr(self.lang, "full_shape_no_shapes"))
            return
        if shape_count > template_count:
            self.log_line(f"{tr(self.lang, 'full_shape_too_many_shapes')} JSON={shape_count}, template={template_count}")
            return
        self.status.set(tr(self.lang, "running"))
        self.full_shape_last_output_dir.set(str(FULL_SHAPE_ROOT))
        threading.Thread(
            target=self._full_shape_import_worker,
            args=(
                pid,
                template_count,
                shape_count,
                json_path,
                self.full_shape_clear_unused.get() == "1",
            ),
            daemon=True,
        ).start()

    def start_full_shape_export(self):
        pid = self.ensure_live_game_pid()
        if not pid:
            return
        template_count = self._full_shape_count_value()
        if not template_count:
            return
        initial_dir = Path(self.full_shape_last_output_dir.get() or FULL_SHAPE_ROOT)
        initial_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = filedialog.asksaveasfilename(
            title=tr(self.lang, "full_shape_export_button"),
            initialdir=initial_dir,
            initialfile=f"fh6-full-shape-export-{template_count}-{timestamp}.json",
            defaultextension=".json",
            filetypes=[("Full-shape JSON", "*.json"), ("All files", "*.*")],
        )
        if not output:
            return
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.full_shape_last_output_dir.set(str(output_path.parent))
        self.status.set(tr(self.lang, "running"))
        threading.Thread(target=self._full_shape_export_worker, args=(pid, template_count, output_path), daemon=True).start()

    def _candidate_shape_count(self, candidate, shape_byte):
        counts = candidate.get("shape_id_counts_all") or {}
        return int(counts.get(str(shape_byte)) or counts.get(shape_byte) or 0)

    def _candidate_rejection(self, candidate, template_count, require_circle_template):
        valid_ptrs = int(candidate.get("valid_ptrs") or 0)
        sample_ok = int(candidate.get("sample_ok_count") or 0)
        min_sample_ok = min(8, int(template_count))
        vector_count = candidate.get("vector_count")
        capacity_count = candidate.get("capacity_count")
        if candidate.get("vector_ok") is False:
            return "vector metadata invalid"
        if vector_count is not None and int(vector_count) != int(template_count):
            return f"vector_count={vector_count}"
        if capacity_count is not None and int(capacity_count) < int(template_count):
            return f"capacity_count={capacity_count}"
        if valid_ptrs < int(template_count):
            return f"valid_ptrs={valid_ptrs}"
        if sample_ok < min_sample_ok:
            return f"sample_ok={sample_ok}"
        if require_circle_template:
            min_circle_count = int(int(template_count) * 0.90)
            circle_count = self._candidate_shape_count(candidate, 102)
            if circle_count < min_circle_count:
                return f"circle_template_check={circle_count}/{template_count}"
        return ""

    def _locate_full_shape_group(self, pid, template_count, run_dir, purpose):
        probe_report = run_dir / f"fallback-{purpose}-probe.json"
        cmd = [
            *helper_command("fh6_typecode_probe"),
            "--pid",
            str(pid),
            "--count",
            str(template_count),
            "--max-seconds",
            "120",
            "--report-layers",
            "40",
            "--out-dir",
            run_dir,
        ]
        self.queue.put(("log", tr(self.lang, "full_shape_probe_wait")))
        code = self.run_subprocess(cmd, timeout=180)
        if code != 0:
            raise RuntimeError("full-shape probe did not complete")
        probe_files = sorted(run_dir.glob(f"fh6-group{template_count}-probe-*.json"), key=lambda path: path.stat().st_mtime)
        if not probe_files:
            raise RuntimeError("full-shape probe report was not created")
        if probe_report.exists():
            probe_report.unlink()
        probe_files[-1].replace(probe_report)
        probe = json.loads(probe_report.read_text(encoding="utf-8"))
        candidates = probe.get("candidates") or []
        if not candidates:
            raise RuntimeError("no matching loaded FH6 group was found")

        require_circle_template = str(purpose).startswith("import")
        rejected = []
        selected = None
        strong_export_candidates = []
        for index, candidate in enumerate(candidates, start=1):
            group = candidate.get("group")
            table = candidate.get("table")
            rejection = self._candidate_rejection(candidate, template_count, require_circle_template)
            if group and table and not rejection and selected is None:
                selected = (index, group, table, int(candidate.get("valid_ptrs") or 0), int(candidate.get("sample_ok_count") or 0), self._candidate_shape_count(candidate, 102))
            else:
                rejected.append(f"#{index}: {rejection or 'missing group/table'}")
            if not require_circle_template and group and table and not rejection:
                signature = (
                    tuple(sorted((candidate.get("shape_id_counts_sample") or {}).items())),
                    tuple(sorted((candidate.get("color_counts_sample") or {}).items())),
                )
                strong_export_candidates.append((index, candidate, signature, int(candidate.get("score") or 0)))

        if not require_circle_template and strong_export_candidates:
            best_score = max(score for _index, _candidate, _signature, score in strong_export_candidates)
            score_floor = best_score - max(10, int(best_score * 0.02))
            seen = {}
            for index, candidate, signature, score in strong_export_candidates:
                if score < score_floor:
                    continue
                previous = seen.get(signature)
                if previous:
                    prev_index, prev_candidate = previous
                    raise RuntimeError(
                        "export refused: duplicate full-strength editable-looking layer tables "
                        f"(#{prev_index} {prev_candidate.get('group')} and #{index} {candidate.get('group')})"
                    )
                seen[signature] = (index, candidate)

        if not selected:
            detail = "; ".join(rejected[:5]) if rejected else "no candidates"
            if require_circle_template:
                raise RuntimeError(tr(self.lang, "full_shape_fresh_template_required").format(detail=detail))
            raise RuntimeError(f"located group did not validate strongly enough ({detail})")
        index, group, table, valid_ptrs, sample_ok, circle_count = selected
        circle_suffix = f", circle_template={circle_count}/{template_count}" if require_circle_template else ""
        self.queue.put(("log", f"FH6 full-shape group located: candidate #{index}, group={group}, table={table}, layers={template_count}, valid_ptrs={valid_ptrs}, sample_ok={sample_ok}{circle_suffix}"))
        return group, table, probe_report

    def _full_shape_import_worker(self, pid, template_count, shape_count, json_path, clear_unused):
        run_dir = self._full_shape_run_dir("import", json_path.stem)
        self.queue.put(("full_shape_report_dir", run_dir))
        backup_path = run_dir / "import-backup.json"
        import_report = run_dir / "import-report.json"
        trim_backup = run_dir / "trim-backup.json"
        try:
            self.queue.put(("log", f"{tr(self.lang, 'full_shape_importing')} shapes={shape_count}, template={template_count}"))
            group, table, _probe_report = self._locate_full_shape_group(pid, template_count, run_dir, "import-template")
            import_cmd = [
                *helper_command("fh6_typecode_import"),
                "--pid",
                str(pid),
                "--table",
                str(table),
                "--json",
                json_path,
                "--template-count",
                str(template_count),
                "--compact-supported-layers",
                "--allow-unknown-low-byte",
                "--backup",
                backup_path,
                "--report",
                import_report,
                "--write",
            ]
            if clear_unused:
                import_cmd.append("--clear-unused")
            code = self.run_subprocess(import_cmd, timeout=360)
            if code != 0:
                self.queue.put(("full_shape_failed_prompt", "import helper exited with an error"))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            report = json.loads(import_report.read_text(encoding="utf-8"))
            imported = int(report.get("imported_layer_count") or 0)
            failures = int(report.get("failure_count") or 0)
            unsupported = int(report.get("unsupported_shape_count") or 0)
            if unsupported:
                self.queue.put(("log", f"Unsupported full-shape rows skipped: {unsupported}"))
            if failures:
                self.queue.put(("log", f"Full-shape import wrote with failures: imported={imported}, failures={failures}"))
                self.queue.put(("full_shape_failed_prompt", f"imported={imported}, failures={failures}"))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            if imported <= 0:
                failure = "Full-shape import failed: no layers were imported."
                self.queue.put(("log", failure))
                self.queue.put(("full_shape_failed_prompt", failure))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            # === TRIM DISABLED: importing now shows results immediately without save/reload ===
            # trim_cmd = [
            #     *helper_command("fh6_typecode_trim"),
            #     "--pid",
            #     str(pid),
            #     "--group",
            #     str(group),
            #     "--table",
            #     str(table),
            #     "--new-count",
            #     str(imported),
            #     "--trim-vector-end",
            #     "--backup",
            #     trim_backup,
            #     "--write",
            # ]
            # code = self.run_subprocess(trim_cmd, timeout=90)
            # if code != 0:
            #     failure = "Full-shape import wrote layers but failed while trimming layer count."
            #     self.queue.put(("log", failure))
            #     self.queue.put(("full_shape_failed_prompt", failure))
            #     self.queue.put(("status", tr(self.lang, "failed")))
            #     return
            self.queue.put(("log", tr(self.lang, "full_shape_import_done").format(count=imported)))
            self.queue.put(("status", tr(self.lang, "done")))
        except Exception as exc:
            self.queue.put(("log", f"{tr(self.lang, 'full_shape_failed')}: {exc}"))
            self.queue.put(("full_shape_failed_prompt", str(exc)))
            self.queue.put(("status", tr(self.lang, "failed")))

    def _full_shape_export_worker(self, pid, template_count, output_path):
        run_dir = self._full_shape_run_dir("export", output_path.stem)
        self.queue.put(("full_shape_report_dir", run_dir))
        self.queue.put(("full_shape_output_dir", output_path.parent))
        export_report = run_dir / "export-report.json"
        try:
            group, table, probe_report = self._locate_full_shape_group(pid, template_count, run_dir, "export-template")
            export_cmd = [
                *helper_command("fh6_typecode_export"),
                "--pid",
                str(pid),
                "--group",
                str(group),
                "--table",
                str(table),
                "--count",
                str(template_count),
                "--out",
                output_path,
                "--report",
                export_report,
                "--probe-report",
                probe_report,
            ]
            code = self.run_subprocess(export_cmd, timeout=360)
            if code != 0:
                prompt_detail = "export helper exited with an error"
                if export_report.exists():
                    try:
                        report = json.loads(export_report.read_text(encoding="utf-8"))
                        refusal = report.get("refusal_reason")
                        reasons = report.get("validation_reasons") or []
                        if refusal:
                            self.queue.put(("log", str(refusal)))
                            prompt_detail = str(refusal)
                        if reasons:
                            self.queue.put(("log", "Export validation: " + "; ".join(str(reason) for reason in reasons[:4])))
                    except Exception:
                        pass
                self.queue.put(("full_shape_failed_prompt", prompt_detail))
                self.queue.put(("status", tr(self.lang, "failed")))
                return
            report = json.loads(export_report.read_text(encoding="utf-8"))
            exported = int(report.get("exported_shape_count") or 0)
            failures = int(report.get("failure_count") or 0)
            if failures:
                self.queue.put(("log", f"Export warning: {failures} unreadable layer(s), see report."))
            self.queue.put(("full_shape_json_path", output_path))
            self.queue.put(("log", tr(self.lang, "full_shape_export_done").format(count=exported, path=output_path)))
            self.queue.put(("status", tr(self.lang, "done")))
        except Exception as exc:
            self.queue.put(("log", f"{tr(self.lang, 'full_shape_failed')}: {exc}"))
            self.queue.put(("full_shape_failed_prompt", str(exc)))
            self.queue.put(("status", tr(self.lang, "failed")))

    def start_diagnose(self):
        pid = self.ensure_live_game_pid()
        cmd = [*helper_command("main"), "--game", self.selected_game.get() or "fh6", "--diagnose"]
        if pid:
            cmd.extend(["--pid", str(pid)])
        self.status.set(tr(self.lang, "running"))
        threading.Thread(target=lambda: self._run_command_worker(cmd, 120), daemon=True).start()

    def start_save_snapshot(self):
        pid = self.ensure_live_game_pid()
        count = self.snapshot_count.get().strip() or self.layer_count.get().strip()
        if not pid or not count:
            self.log_line("PID and snapshot layer count are required.")
            return
        output_path = PROBE_DIR / f"memory-count-{count}.jsonl"
        cmd = [
            *helper_command("fh6_probe"),
            "--game",
            self.selected_game.get() or "fh6",
            "--pid",
            str(pid),
            "--layer-count",
            str(count),
            "--save-memory-snapshot",
            output_path,
            "--limit-mb",
            str(MEMORY_SNAPSHOT_LIMIT_MB),
        ]
        self.status.set(tr(self.lang, "running"))
        threading.Thread(target=lambda: self._run_command_worker(cmd, 360), daemon=True).start()

    def start_compare_snapshot(self):
        pid = self.ensure_live_game_pid()
        previous = self.snapshot_count.get().strip()
        current = self.current_count.get().strip() or self.layer_count.get().strip()
        if not pid or not previous or not current:
            self.log_line("PID, snapshot layer count, and current layer count are required.")
            return
        snapshot_path = PROBE_DIR / f"memory-count-{previous}.jsonl"
        candidates_path = PROBE_DIR / f"memory-count-{previous}-to-{current}-candidates.json"
        intersect_path = PROBE_DIR / f"memory-count-{int(previous) - 1}-to-{previous}-candidates.json"
        cmd = [
            *helper_command("fh6_probe"),
            "--game",
            self.selected_game.get() or "fh6",
            "--pid",
            str(pid),
            "--layer-count",
            str(current),
            "--compare-memory-snapshot",
            snapshot_path,
            "--write-candidates",
            candidates_path,
            "--max-matches",
            "50000",
        ]
        if intersect_path.exists():
            cmd.extend(["--intersect-candidates", intersect_path])
        self.status.set(tr(self.lang, "running"))
        threading.Thread(target=lambda: self._run_command_worker(cmd, 360), daemon=True).start()

    def start_inspect_table(self):
        pid = self.ensure_live_game_pid()
        table = self.inspect_table_value.get().strip()
        count = self.layer_count.get().strip()
        if not pid or not table or not count:
            self.log_line("PID, layer count, and table address are required.")
            return
        cmd = [
            *helper_command("fh6_probe"),
            "--game",
            self.selected_game.get() or "fh6",
            "--pid",
            str(pid),
            "--layer-count",
            str(count),
            "--inspect-table",
            table,
            "--inspect-layers",
            "12",
        ]
        self.status.set(tr(self.lang, "running"))
        threading.Thread(target=lambda: self._run_command_worker(cmd, 60), daemon=True).start()

    def _run_command_worker(self, cmd, timeout):
        code = self.run_subprocess(cmd, timeout=timeout)
        self.queue.put(("status", tr(self.lang, "done") if code == 0 else tr(self.lang, "failed")))

    def _poll_queue(self):
        if self.closed:
            return
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log_line(payload)
            elif kind == "progress":
                self.progress_text.set(payload)
            elif kind == "status":
                self.status.set(payload)
            elif kind == "generation_done":
                stopped = self.shutdown_event.is_set()
                with self.generation_lock:
                    self.generation_running = False
                    self.current_generator_proc = None
                if hasattr(self, "generate_button"):
                    self.generate_button.config(state="normal")
                if hasattr(self, "stop_generate_button"):
                    self.stop_generate_button.config(state="disabled")
                if stopped and not self.closed:
                    self.progress_text.set(tr(self.lang, "generation_stopped"))
                    self.status.set(tr(self.lang, "stopped"))
                    self.log_line(tr(self.lang, "generation_stopped"))
            elif kind == "preview":
                self.show_preview(payload)
            elif kind == "preview_rendered":
                token, request, cache_key, data = payload
                if token == self.preview_render_token and request == self.current_preview_request:
                    self._remember_preview_cache(cache_key, data)
                    self.preview_display_cache_key = (cache_key, id(self._active_preview_label())) if data else None
                    self.show_preview(data)
            elif kind == "preview_json":
                self.show_json_preview(payload)
            elif kind == "preview_file":
                self.show_preview_file(payload)
            elif kind == "render_lists":
                self._render_lists()
            elif kind == "update_failed":
                self._handle_update_failed(payload)
            elif kind == "update_current":
                self._handle_update_current(payload)
            elif kind == "update_available":
                self._handle_update_available(payload)
            elif kind == "full_shape_json_path":
                self.full_shape_json_path.set(str(payload))
            elif kind == "full_shape_output_dir":
                self.full_shape_last_output_dir.set(str(payload))
            elif kind == "full_shape_report_dir":
                self.full_shape_last_report_dir.set(str(payload))
                if hasattr(self, "full_shape_report_button"):
                    self.full_shape_report_button.config(state="normal")
            elif kind == "full_shape_failed_prompt":
                self.show_full_shape_failure_prompt(payload)
            elif kind == "region_log":
                self.log_line(payload)
            elif kind == "region_progress":
                self.region_progress.set(payload)
            elif kind == "region_preview":
                # Live preview from exe during generation
                try:
                    self._region_display_preview(Path(payload))
                except Exception:
                    pass
            elif kind == "region_status":
                self.region_status.set(payload)
                self.region_workflow_running = False
                self._region_update_button_states()
            elif kind == "region_done":
                self.region_workflow_running = False
                self.shutdown_event.clear()
                result = payload or {}
                if result.get("ok"):
                    self.region_status.set(tr(self.lang, "done"))
                    self.region_progress.set("")
                    if result.get("new_total"):
                        self.region_progress.set(f"Total layers: {result['new_total']}")
                    # Refresh pass history
                    pass_label = "complete"
                    if self.region_current_output_dir:
                        try:
                            status = region_get_status(self.region_current_output_dir)
                            self.region_pass_list.delete(0, END)
                            for i, p in enumerate(status.get("passes", []), 1):
                                label = f"#{i}: {p.get('layers', 0)} layers"
                                if p.get("mask"):
                                    label += " (region)"
                                else:
                                    label += " (first pass)"
                                self.region_pass_list.insert(END, label)
                            # Capture last pass info for logging
                            passes = status.get("passes", [])
                            if passes:
                                last = passes[-1]
                                pass_type = "region pass" if last.get("mask") else "first pass"
                                pass_label = f"Pass #{len(passes)} {pass_type} complete — {last.get('layers', 0)} layers"
                            self.region_remaining_var.set(str(status.get("remaining", 0)))
                        except Exception:
                            pass
                    self.log_line(f"Region Paint: {pass_label}")
                    # Auto-clear mask first (same as pressing "Clear Mask" button)
                    self._region_clear_mask()
                    # Show preview if available
                    preview_path = result.get("preview_path")
                    if not preview_path:
                        preview_path = Path(self.region_current_output_dir) / "preview.png"
                    else:
                        preview_path = Path(preview_path)
                    if preview_path.exists():
                        if self._region_right_tab == "preview":
                            self._region_display_preview(preview_path)
                        else:
                            # Cache preview so it's ready when user switches tab
                            self._region_preview_showing = str(preview_path)
                    # Handle heatmap
                    heatmap_path = result.get("heatmap_path")
                    if heatmap_path:
                        heatmap_p = Path(heatmap_path)
                        if heatmap_p.exists():
                            if self._region_right_tab == "heatmap":
                                self._region_display_heatmap(heatmap_p)
                            else:
                                # Cache the path so it's ready on tab switch
                                self._region_heatmap_showing = str(heatmap_p)
                            if self.region_tab_heatmap_btn:
                                self.region_tab_heatmap_btn.config(fg=Theme.TEXT, cursor="hand2")
                else:
                    self.region_status.set(tr(self.lang, "failed"))
                    self.region_progress.set(result.get("error", "Unknown error"))
                    self.log_line(f"Region Paint: failed — {result.get('error', 'Unknown error')}")
                self._region_update_button_states()
            elif kind == "region_canvas_update":
                self._region_display_image(payload)
        if not self.closed:
            self.root.after(100, self._poll_queue)

    def run(self):
        self.root.mainloop()


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--helper":
        run_embedded_helper(sys.argv[2], sys.argv[3:])
        return
    parser = argparse.ArgumentParser(description=f"Standalone {APP_DISPLAY_NAME} desktop app.")
    parser.add_argument("--version", action="version", version=f"{APP_DISPLAY_NAME} {__version__}")
    parser.add_argument("images", nargs="*", help="Optional image files to preload.")
    args = parser.parse_args()
    App(args.images).run()


if __name__ == "__main__":
    main()
