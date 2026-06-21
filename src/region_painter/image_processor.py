"""Image processing utilities for region-focused painting.

Handles: blank mask creation, canvas-shape 鈫?PIL mask conversion, and
alpha-channel masking (apply selection mask to target images).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def create_blank_mask(width: int, height: int) -> Image.Image:
    """Return a blank (all zeros) ``'L'`` mode mask at *width* 脳 *height*."""
    return Image.new("L", (width, height), 0)


def mask_from_canvas_shapes(
    shapes: list[dict],
    width: int,
    height: int,
    scale: float = 1.0,
) -> Image.Image:
    """Convert a list of canvas-selection shape dicts into a PIL ``'L'`` mask.

    Each shape dict must have:
        ``"tool"``: one of ``"rect"``, ``"ellipse"``, ``"brush"``, ``"polygon"``
        ``"coords"``: tool-specific coordinate list (in *canvas* pixels)
        ``"rotation"``: (rect/ellipse) rotation in degrees (default 0)
        ``"brush_size"``: (brush only) stroke width in canvas pixels
        ``"exclude"``: if True, the shape is an exclusion zone (painted black).

    Coordinates are divided by *scale* to map from canvas space to working
    (full-resolution) pixel space.

    Include shapes are drawn first (white), then exclude shapes are drawn
    on top (black), so exclude takes priority in overlapping regions.
    """
    mask = create_blank_mask(width, height)
    draw = ImageDraw.Draw(mask)

    # Try OpenCV for rotated shapes
    try:
        from utils import load_cv2
        loaded = load_cv2()
        cv2_mod, np_mod = (loaded if loaded else (None, None))
    except Exception:
        cv2_mod, np_mod = None, None

    # Separate include and exclude shapes; process include first, exclude second.
    include_shapes = [s for s in shapes if not s.get("exclude", False)]
    exclude_shapes = [s for s in shapes if s.get("exclude", False)]

    has_rotated = any(s.get("rotation", 0) != 0 for s in shapes)
    cv2_mask = None
    if cv2_mod is not None and np_mod is not None and has_rotated:
        cv2_mask = np_mod.zeros((height, width), dtype=np_mod.uint8)

    # --- Pass 1: draw include shapes (white = 255) ---
    for shape in include_shapes:
        _draw_shape_on_mask(shape, scale, draw, cv2_mod, cv2_mask, fill=255)

    # Merge OpenCV mask back into PIL mask before exclude pass
    if cv2_mask is not None:
        mask_np = np_mod.array(mask)
        mask_np[cv2_mask > 0] = 255
        mask = Image.fromarray(mask_np, mode="L")

    # --- Pass 2: draw exclude shapes (black = 0) on top ---
    if exclude_shapes:
        draw = ImageDraw.Draw(mask)
        cv2_mask_ex = None
        if cv2_mod is not None and np_mod is not None and has_rotated:
            cv2_mask_ex = np_mod.zeros((height, width), dtype=np_mod.uint8)
        for shape in exclude_shapes:
            _draw_shape_on_mask(shape, scale, draw, cv2_mod, cv2_mask_ex, fill=0)
        if cv2_mask_ex is not None:
            mask_np = np_mod.array(mask)
            mask_np[cv2_mask_ex > 0] = 0
            mask = Image.fromarray(mask_np, mode="L")

    return mask


def _draw_shape_on_mask(
    shape: dict,
    scale: float,
    draw: ImageDraw.ImageDraw,
    cv2_mod,
    cv2_mask,
    fill: int = 255,
) -> None:
    """Draw a single shape onto a PIL mask and optional OpenCV mask."""
    tool = shape.get("tool", "")
    coords = shape.get("coords", [])
    rotation = shape.get("rotation", 0)

    # Lazy-load numpy for astype in boxPoints
    np_mod = None
    if cv2_mask is not None:
        try:
            import numpy as np_mod
        except Exception:
            pass

    # Scale coords from canvas → working pixels.
    scaled: list[float] = [c / scale for c in coords]

    if tool == "rect" and len(scaled) >= 4:
        x1, y1, x2, y2 = scaled[:4]
        if rotation != 0 and cv2_mask is not None and np_mod is not None:
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            hw = abs(x2 - x1) / 2.0
            hh = abs(y2 - y1) / 2.0
            rect = ((cx, cy), (hw * 2, hh * 2), rotation)
            box = cv2_mod.boxPoints(rect).astype(np_mod.int32)
            cv2_mod.fillPoly(cv2_mask, [box], fill)
        else:
            draw.rectangle([x1, y1, x2, y2], fill=fill)

    elif tool == "ellipse" and len(scaled) >= 4:
        x1, y1, x2, y2 = scaled[:4]
        if rotation != 0 and cv2_mask is not None:
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            hw = abs(x2 - x1) / 2.0
            hh = abs(y2 - y1) / 2.0
            cv2_mod.ellipse(cv2_mask,
                            (int(round(cx)), int(round(cy))),
                            (int(round(hw)), int(round(hh))),
                            rotation, 0.0, 360.0, fill, thickness=-1)
        else:
            draw.ellipse([x1, y1, x2, y2], fill=fill)

    elif tool == "brush":
        brush_size = shape.get("brush_size", 15) / scale
        # Convert flat [x1,y1,x2,y2,...] into (x,y) pairs.
        points: list[tuple[float, float]] = []
        for i in range(0, len(scaled) - 1, 2):
            points.append((scaled[i], scaled[i + 1]))
        if len(points) >= 2:
            draw.line(points, fill=fill, width=max(1, int(round(brush_size))))
        elif len(points) == 1:
            # Single click → draw a dot.
            x, y = points[0]
            r = max(1, int(round(brush_size / 2)))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    elif tool == "polygon" and len(scaled) >= 6:
        points = [(scaled[i], scaled[i + 1]) for i in range(0, len(scaled) - 1, 2)]
        if len(points) >= 3:
            draw.polygon(points, fill=fill)


def apply_selection_mask(
    target_path: str | Path,
    mask: Image.Image,
    output_path: str | Path,
    feather_radius: int = 0,
) -> None:
    """Apply a selection mask to *target_path*, writing to *output_path*.

    1. Load target RGBA PNG.
    2. Optionally Gaussian-blur the mask (*feather_radius* > 0).
    3. Multiply mask into the alpha channel:
       ``new_alpha = original_alpha * (mask_pixel / 255)``
    4. Save as RGBA PNG.
    """
    target_path = Path(target_path)
    output_path = Path(output_path)

    target = Image.open(target_path).convert("RGBA")

    # Ensure mask matches target dimensions.
    if mask.size != target.size:
        mask = mask.resize(target.size, Image.NEAREST)

    if feather_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))

    # Multiply mask into alpha channel.
    r, g, b, a = target.split()
    # mask is 'L' (0-255); use it as a multiplier.
    mask_data = mask.point(lambda v: v)  # copy
    new_alpha = Image.composite(
        Image.new("L", target.size, 0),
        a,
        mask_data,
    )
    # Actually: new_alpha = a * (mask / 255)
    # We can do this via point operations.
    a_pixels = a.load()
    m_pixels = mask_data.load()
    for y in range(target.height):
        for x in range(target.width):
            a_val = a_pixels[x, y]
            m_val = m_pixels[x, y]
            a_pixels[x, y] = int(a_val * (m_val / 255.0))

    result = Image.merge("RGBA", (r, g, b, a))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, "PNG")
