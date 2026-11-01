"""Tests for the generate-page output layout (image/<ext>/ backup, out/<stem>/<ext>/ JSONs)."""

from __future__ import annotations

import threading

import pytest

from generator_backend import (
    generated_jsons,
    generator_output_base,
    prepare_generation_copies,
)


@pytest.fixture
def dirs(tmp_path):
    return tmp_path / "image", tmp_path / "out"


def _write_image(path, payload: bytes = b"png-bytes"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class TestPrepareGenerationCopies:
    def test_backup_lands_in_extension_folder_and_out_holds_no_image(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        source = _write_image(tmp_path / "sources" / "doro1.png")

        backup, output_folder = prepare_generation_copies(source, image_dir, output_dir)

        assert backup == image_dir / "png" / "doro1.png"
        assert backup.read_bytes() == b"png-bytes"
        assert output_folder == output_dir / "doro1" / "png"
        assert list(output_folder.iterdir()) == []
        assert not list(output_dir.rglob("*.png"))

    def test_generator_output_lands_in_the_extension_folder(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        source = _write_image(tmp_path / "sources" / "doro1.png")
        backup, _ = prepare_generation_copies(source, image_dir, output_dir)

        # The generator writes to the explicit -output base; checkpoints must
        # land inside out/<stem>/<ext>/.
        base = generator_output_base(backup, output_dir)
        assert base == output_dir / "doro1" / "png" / "doro1"

        final_json = base.with_suffix(".json")
        final_json.write_text("{}", encoding="utf-8")
        checkpoint = base.with_name("doro1.500.json")
        checkpoint.write_text("{}", encoding="utf-8")

        found = {path.name for path in generated_jsons(backup, output_dir)}
        assert {"doro1.json", "doro1.500.json"} <= found

    def test_regenerating_the_same_image_reuses_paths(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        source = _write_image(tmp_path / "sources" / "doro1.png")

        first = prepare_generation_copies(source, image_dir, output_dir)
        second = prepare_generation_copies(source, image_dir, output_dir)

        assert first == second
        assert len([path for path in image_dir.rglob("*") if path.is_file()]) == 1

    def test_same_name_same_extension_different_content_is_rejected(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        first = _write_image(tmp_path / "a" / "doro1.png", b"first-image")
        second = _write_image(tmp_path / "b" / "doro1.png", b"second-image")

        prepare_generation_copies(first, image_dir, output_dir)
        with pytest.raises(ValueError):
            prepare_generation_copies(second, image_dir, output_dir)

        assert (image_dir / "png" / "doro1.png").read_bytes() == b"first-image"

    def test_jpg_and_png_of_one_stem_are_isolated(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        png = _write_image(tmp_path / "a" / "doro1.png", b"png-image")
        jpg = _write_image(tmp_path / "b" / "doro1.jpg", b"jpg-image")

        backup_png, folder_png = prepare_generation_copies(png, image_dir, output_dir)
        backup_jpg, folder_jpg = prepare_generation_copies(jpg, image_dir, output_dir)

        assert backup_png == image_dir / "png" / "doro1.png"
        assert backup_jpg == image_dir / "jpg" / "doro1.jpg"
        assert folder_png == output_dir / "doro1" / "png"
        assert folder_jpg == output_dir / "doro1" / "jpg"

        (folder_png / "doro1.json").write_text("{}", encoding="utf-8")
        (folder_jpg / "doro1.json").write_text("{}", encoding="utf-8")

        found_png = generated_jsons(backup_png, output_dir)
        found_jpg = generated_jsons(backup_jpg, output_dir)
        assert folder_png / "doro1.json" in found_png
        assert all(path.parent != folder_jpg for path in found_png)
        assert folder_jpg / "doro1.json" in found_jpg
        assert all(path.parent != folder_png for path in found_jpg)

    def test_upper_case_extension_uses_the_same_folders(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        source = _write_image(tmp_path / "sources" / "doro1.PNG")

        backup, output_folder = prepare_generation_copies(source, image_dir, output_dir)

        assert backup == image_dir / "png" / "doro1.PNG"
        assert output_folder == output_dir / "doro1" / "png"
        assert generator_output_base(backup, output_dir) == output_dir / "doro1" / "png" / "doro1"

    def test_source_already_archived_is_not_copied_onto_itself(self, dirs):
        image_dir, output_dir = dirs
        source = _write_image(image_dir / "png" / "doro1.png")

        backup, output_folder = prepare_generation_copies(source, image_dir, output_dir)

        assert backup == source
        assert output_folder == output_dir / "doro1" / "png"


class TestLegacyOutFolder:
    def test_legacy_jsons_in_the_stem_root_are_still_found(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        source = _write_image(tmp_path / "sources" / "doro1.png")
        backup, _ = prepare_generation_copies(source, image_dir, output_dir)
        legacy_json = output_dir / "doro1" / "doro1.json"
        legacy_json.write_text("{}", encoding="utf-8")

        assert legacy_json in generated_jsons(backup, output_dir)

    def test_matching_legacy_image_copy_is_removed_from_out(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        source = _write_image(tmp_path / "sources" / "doro1.png")
        legacy = _write_image(output_dir / "doro1" / "doro1.png", b"png-bytes")

        prepare_generation_copies(source, image_dir, output_dir)

        assert not legacy.exists()

    def test_different_legacy_image_copy_is_kept(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        source = _write_image(tmp_path / "sources" / "doro1.png")
        legacy = _write_image(output_dir / "doro1" / "doro1.png", b"something-else")

        prepare_generation_copies(source, image_dir, output_dir)

        assert legacy.exists()


class TestConcurrentCopyAllocation:
    def test_parallel_conflicting_copies_are_serialized(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        first = _write_image(tmp_path / "a" / "doro1.png", b"first-image")
        second = _write_image(tmp_path / "b" / "doro1.png", b"second-image")
        barrier = threading.Barrier(2, timeout=30)
        results = {}

        def run(key, source):
            barrier.wait()
            try:
                results[key] = prepare_generation_copies(source, image_dir, output_dir)
            except ValueError as exc:
                results[key] = exc

        threads = [
            threading.Thread(target=run, args=("one", first)),
            threading.Thread(target=run, args=("two", second)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)

        outcomes = list(results.values())
        errors = [outcome for outcome in outcomes if isinstance(outcome, ValueError)]
        successes = [outcome for outcome in outcomes if not isinstance(outcome, ValueError)]
        assert len(errors) == 1
        assert len(successes) == 1
        backup, _folder = successes[0]
        assert backup.read_bytes() in (b"first-image", b"second-image")
        assert len(list((image_dir / "png").iterdir())) == 1
        assert not list(output_dir.rglob("*.png"))

    def test_parallel_identical_copies_share_one_backup(self, dirs, tmp_path):
        image_dir, output_dir = dirs
        first = _write_image(tmp_path / "a" / "doro1.png", b"same-bytes")
        second = _write_image(tmp_path / "b" / "doro1.png", b"same-bytes")
        barrier = threading.Barrier(2, timeout=30)
        results = {}

        def run(key, source):
            barrier.wait()
            results[key] = prepare_generation_copies(source, image_dir, output_dir)

        threads = [
            threading.Thread(target=run, args=("one", first)),
            threading.Thread(target=run, args=("two", second)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)

        assert len(results) == 2
        backup, _folder = results["one"]
        assert results["one"] == results["two"]
        assert backup.read_bytes() == b"same-bytes"
        assert len(list((image_dir / "png").iterdir())) == 1
        assert not list(output_dir.rglob("*.png"))
