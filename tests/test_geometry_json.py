from __future__ import annotations

import json
import pytest
from pathlib import Path

from geometry_json import (
    ShapeType,
    RECTANGLE,
    ROTATED_ELLIPSE,
    normalize_geometry_payload,
    drawable_shape_count,
)
from utils import clamp_byte


class TestShapeTypeEnum:
    def test_members(self):
        assert ShapeType.RECTANGLE == 1
        assert ShapeType.ROTATED_ELLIPSE == 16

    def test_backward_compat_aliases(self):
        assert RECTANGLE is ShapeType.RECTANGLE
        assert ROTATED_ELLIPSE is ShapeType.ROTATED_ELLIPSE

    def test_int_comparable(self):
        assert ShapeType.RECTANGLE == 1
        assert ShapeType.ROTATED_ELLIPSE == 16


class TestNormalizeGeometryPayload:
    def test_rectangle_only(self):
        payload = [
            {"type": 1, "data": [0, 0, 100, 200], "color": [255, 0, 0, 255]},
        ]
        result = normalize_geometry_payload(payload)
        assert result["shapes"][0]["type"] == ShapeType.RECTANGLE
        assert result["shapes"][0]["data"] == [0, 0, 100, 200]

    def test_rotated_ellipse(self):
        payload = [
            {"type": 16, "data": [50, 50, 30, 20, 45], "color": [0, 255, 0, 128]},
        ]
        result = normalize_geometry_payload(payload)
        assert result["shapes"][1]["type"] == ShapeType.ROTATED_ELLIPSE
        assert result["shapes"][1]["data"] == [50, 50, 30, 20, 45]

    def test_unsupported_shape_is_filtered(self):
        payload = [
            {"type": 99, "data": [0, 0, 10, 10], "color": [0, 0, 0, 255]},
        ]
        with pytest.raises(ValueError, match="supported shapes"):
            normalize_geometry_payload(payload)

    def test_empty_payload(self):
        with pytest.raises(ValueError, match="does not contain shapes"):
            normalize_geometry_payload([])

    def test_background_detection(self):
        payload = [
            {"type": 1, "data": [0, 0, 100, 200], "color": [0, 0, 0, 0]},
            {"type": 16, "data": [50, 50, 10, 10, 0], "color": [255, 255, 255, 255]},
        ]
        result = normalize_geometry_payload(payload)
        assert len(result["shapes"]) == 2
        assert result["shapes"][0]["color"] == [0, 0, 0, 0]

    def test_dict_payload_with_shapes_key(self):
        payload = {
            "width": 100,
            "height": 200,
            "shapes": [
                {"type": 1, "data": [0, 0, 100, 200], "color": [0, 0, 0, 0]},
                {"type": 16, "data": [50, 50, 10, 10, 0], "color": [255, 0, 0, 255]},
            ],
        }
        result = normalize_geometry_payload(payload)
        assert len(result["shapes"]) == 2


class TestDrawableShapeCount:
    def test_counts_drawable_shapes(self, tmp_path: Path):
        payload = [
            {"type": 1, "data": [0, 0, 100, 200], "color": [0, 0, 0, 0]},  # bg
            {"type": 16, "data": [50, 50, 10, 10, 0], "color": [255, 0, 0, 255]},
            {"type": 16, "data": [60, 60, 10, 10, 0], "color": [0, 255, 0, 0]},  # transparent
            {"type": 1, "data": [70, 70, 10, 10], "color": [0, 0, 255, 255]},
        ]
        path = tmp_path / "test.json"
        path.write_text(json.dumps(payload))
        assert drawable_shape_count(path) == 2

    def test_invalid_json_returns_zero(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        assert drawable_shape_count(path) == 0


class TestNormalizeColor:
    @pytest.mark.parametrize("color", [
        [0.5, 0.25, 1.0],
        {"r": 0.5, "g": 0.25, "b": 1.0},
        {"Red": 0.5, "Green": 0.25, "Blue": 1.0},
    ])
    def test_normalized_rgb_defaults_to_opaque(self, color):
        from geometry_json import _normalize_color
        assert _normalize_color(color) == [128, 64, 255, 255]

    def test_rgb_object_is_not_dropped_from_geometry(self):
        payload = [{"type": 16, "data": [50, 50, 10, 10, 0],
                    "color": {"r": 128, "g": 64, "b": 32}}]
        result = normalize_geometry_payload(payload)
        assert result["shapes"][1]["color"] == [128, 64, 32, 255]

    @pytest.mark.parametrize("color", [
        {"r": 128, "g": 64, "b": 32, "a": 0},
        [128, 64, 32, 0],
    ])
    def test_explicit_zero_alpha_is_preserved(self, color):
        from geometry_json import _normalize_color
        assert _normalize_color(color) == [128, 64, 32, 0]

    def test_normalize_0_1_range(self):
        from geometry_json import _normalize_color
        assert _normalize_color([0.5, 0.5, 0.5, 1.0]) == [128, 128, 128, 255]

    def test_normalize_0_255_range(self):
        from geometry_json import _normalize_color
        assert _normalize_color([128, 64, 32, 255]) == [128, 64, 32, 255]

    def test_missing_alpha_defaults_to_255(self):
        from geometry_json import _normalize_color
        assert _normalize_color([255, 0, 0]) == [255, 0, 0, 255]

    def test_invalid_returns_none(self):
        from geometry_json import _normalize_color
        assert _normalize_color("invalid") is None


class TestClampByte:
    def test_clamps_negative(self):
        assert clamp_byte(-10) == 0

    def test_clamps_overflow(self):
        assert clamp_byte(300) == 255

    def test_rounds_correctly(self):
        assert clamp_byte(127.4) == 127
        assert clamp_byte(127.5) == 128
