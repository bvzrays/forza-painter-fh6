"""Tests for the same-name-same-extension rule on the generate page."""

from __future__ import annotations

from pathlib import Path

from utils import drop_duplicate_image_names, image_name_key, is_duplicate_image_name


def test_same_stem_and_extension_is_a_duplicate_regardless_of_folder(tmp_path):
    first = tmp_path / "a" / "mabynotimage.png"
    second = tmp_path / "b" / "mabynotimage.png"
    assert is_duplicate_image_name(second, [first])


def test_extension_case_is_normalized(tmp_path):
    assert is_duplicate_image_name(tmp_path / "mabynotimage.PNG", [tmp_path / "x" / "mabynotimage.png"])
    assert is_duplicate_image_name(tmp_path / "mabynotimage.JPG", [tmp_path / "x" / "mabynotimage.jpg"])


def test_different_extension_is_allowed(tmp_path):
    assert not is_duplicate_image_name(tmp_path / "mabynotimage.jpg", [tmp_path / "mabynotimage.png"])


def test_unsupported_extensions_keep_existing_behaviour(tmp_path):
    assert image_name_key(tmp_path / "mabynotimage.bmp") is None
    assert not is_duplicate_image_name(tmp_path / "mabynotimage.bmp", [tmp_path / "x" / "mabynotimage.bmp"])


def test_drop_keeps_first_occurrence_and_unsupported_files():
    paths = [
        Path("a/mabynotimage.png"),
        Path("b/mabynotimage.PNG"),
        Path("c/mabynotimage.jpg"),
        Path("d/mabynotimage.bmp"),
        Path("e/mabynotimage.png"),
    ]
    kept = drop_duplicate_image_names(paths)
    assert kept == [Path("a/mabynotimage.png"), Path("c/mabynotimage.jpg"), Path("d/mabynotimage.bmp")]
