from __future__ import annotations

import json
from enum import IntEnum
from pathlib import Path

from utils import clamp_byte


class ShapeType(IntEnum):
    RECTANGLE = 1
    ROTATED_ELLIPSE = 16


# Backwards-compatible module-level aliases.
RECTANGLE = ShapeType.RECTANGLE
ROTATED_ELLIPSE = ShapeType.ROTATED_ELLIPSE


TYPE_ALIASES = {
    "1": ShapeType.RECTANGLE,
    "rect": ShapeType.RECTANGLE,
    "rectangle": ShapeType.RECTANGLE,
    "box": ShapeType.RECTANGLE,
    "16": ShapeType.ROTATED_ELLIPSE,
    "ellipse": ShapeType.ROTATED_ELLIPSE,
    "ellipsis": ShapeType.ROTATED_ELLIPSE,
    "rotatedellipse": ShapeType.ROTATED_ELLIPSE,
    "rotated_ellipse": ShapeType.ROTATED_ELLIPSE,
    "rotated ellipsis": ShapeType.ROTATED_ELLIPSE,
    "rotated ellipse": ShapeType.ROTATED_ELLIPSE,
}


def load_geometry_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_geometry_payload(payload):
    shapes = _extract_shapes(payload)
    if not shapes:
        raise ValueError("geometry JSON does not contain shapes")

    normalized = []
    for shape in shapes:
        normalized_shape = _normalize_shape(shape)
        if normalized_shape:
            normalized.append(normalized_shape)
    if not normalized:
        raise ValueError("geometry JSON does not contain supported shapes")

    first = normalized[0]
    if _looks_like_background(first):
        background = first
        drawables = normalized[1:]
    else:
        width, height = _infer_size(payload, normalized)
        background = {
            "type": ShapeType.RECTANGLE,
            "data": [0, 0, width, height],
            "color": [0, 0, 0, 0],
            "score": 0,
        }
        drawables = normalized

    return {"shapes": [background] + drawables}


def load_normalized_geometry(path):
    return normalize_geometry_payload(load_geometry_payload(path))


def drawable_shape_count(path):
    try:
        data = load_normalized_geometry(path)
    except Exception:
        return 0
    count = 0
    for shape in data.get("shapes", [])[1:]:
        color = shape.get("color", [])
        if len(color) == 4 and int(color[3]) <= 0:
            continue
        if int(shape.get("type", 0)) in (ShapeType.RECTANGLE, ShapeType.ROTATED_ELLIPSE):
            count += 1
    return count


def _extract_shapes(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("shapes", "Shapes", "geometry", "Geometry", "items", "Items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            if "shapes" in value or "Shapes" in value:
                return _extract_shapes(value)
            items = list(value.items())
            if all(str(k).isdigit() for k, _v in items):
                return [v for _k, v in sorted(items, key=lambda item: int(item[0]))]
    return []


def _normalize_shape(shape):
    if not isinstance(shape, dict):
        return None
    type_id = _normalize_type(_pick(shape, "type", "Type", "shapeType", "ShapeType", "primitive", "Primitive"))
    if type_id not in (ShapeType.RECTANGLE, ShapeType.ROTATED_ELLIPSE):
        return None
    data = _normalize_data(shape, type_id)
    color = _normalize_color(_pick(shape, "color", "Color", "colour", "Colour", "rgba", "RGBA"))
    if not data or not color:
        return None
    return {
        "type": type_id,
        "data": data,
        "color": color,
        "score": _pick(shape, "score", "Score") or 0,
    }


def _normalize_type(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    key = str(value).strip().lower().replace("-", "_")
    key = " ".join(key.split())
    return TYPE_ALIASES.get(key) or TYPE_ALIASES.get(key.replace(" ", "_"))


def _normalize_data(shape, type_id):
    data = _pick(shape, "data", "Data")
    if isinstance(data, dict):
        x = _pick(data, "x", "X", "cx", "centerX", "center_x")
        y = _pick(data, "y", "Y", "cy", "centerY", "center_y")
        w = _pick(data, "w", "W", "width", "Width", "rx", "radiusX", "radius_x")
        h = _pick(data, "h", "H", "height", "Height", "ry", "radiusY", "radius_y")
        rot = _pick(data, "rot", "Rot", "rotation", "Rotation", "angle", "Angle", "theta", "Theta") or 0
        values = [x, y, w, h, rot]
    elif isinstance(data, (list, tuple)):
        values = list(data)
    else:
        x = _pick(shape, "x", "X", "cx", "centerX", "center_x")
        y = _pick(shape, "y", "Y", "cy", "centerY", "center_y")
        w = _pick(shape, "w", "W", "width", "Width", "rx", "radiusX", "radius_x")
        h = _pick(shape, "h", "H", "height", "Height", "ry", "radiusY", "radius_y")
        rot = _pick(shape, "rot", "Rot", "rotation", "Rotation", "angle", "Angle", "theta", "Theta") or 0
        values = [x, y, w, h, rot]

    if len(values) < 4:
        return None
    try:
        x, y, w, h = [float(v) for v in values[:4]]
        rot = float(values[4]) if len(values) >= 5 else 0.0
    except (TypeError, ValueError):
        return None

    if type_id == ShapeType.RECTANGLE:
        return [round(x), round(y), max(0.0, w), max(0.0, h)]
    return [round(x), round(y), max(1.0, w), max(1.0, h), round(rot) % 360]


def _normalize_color(value):
    if isinstance(value, dict):
        values = [
            _pick(value, "r", "R", "red", "Red"),
            _pick(value, "g", "G", "green", "Green"),
            _pick(value, "b", "B", "blue", "Blue"),
        ]
        if any(key in value for key in ("a", "A", "alpha", "Alpha")):
            values.append(_pick(value, "a", "A", "alpha", "Alpha"))
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return None
    if len(values) < 3:
        return None
    try:
        nums = [float(v) for v in values[:4]]
    except (TypeError, ValueError):
        return None
    if all(0.0 <= v <= 1.0 for v in nums):
        nums = [v * 255.0 for v in nums]
    # Infer the input range before adding opaque alpha to RGB colors.
    if len(nums) == 3:
        nums.append(255)
    return [clamp_byte(v) for v in nums]


def _looks_like_background(shape):
    if int(shape.get("type", 0)) != ShapeType.RECTANGLE:
        return False
    data = shape.get("data", [])
    if len(data) != 4:
        return False
    return int(data[0]) == 0 and int(data[1]) == 0 and int(data[2]) > 0 and int(data[3]) > 0


def _infer_size(payload, shapes):
    width = _pick(payload, "width", "Width", "imageWidth", "image_width") if isinstance(payload, dict) else None
    height = _pick(payload, "height", "Height", "imageHeight", "image_height") if isinstance(payload, dict) else None
    try:
        width = int(width)
        height = int(height)
        if width > 0 and height > 0:
            return width, height
    except (TypeError, ValueError):
        pass

    max_x = 1
    max_y = 1
    for shape in shapes:
        data = shape.get("data", [])
        if len(data) < 4:
            continue
        x, y, w, h = [abs(int(v)) for v in data[:4]]
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)
    return max_x, max_y


def _pick(mapping, *keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


# _clamp_byte has moved to utils.clamp_byte for shared use.
