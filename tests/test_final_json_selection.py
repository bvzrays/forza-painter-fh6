"""Generate-page selection behaviour: only the run's final JSON is auto-imported.

These tests bind the real ``App`` selection methods to a stub, so the whole
success/failure/stopped flow runs without Tk or a real generator. Output and
image directories are redirected into the pytest tmp dir; the repository's
own ``out/`` is never touched.
"""

from __future__ import annotations

import io
import threading
import types
from pathlib import Path

import pytest

pytest.importorskip("tkinter")

import app as app_module
from generator_backend import (
    final_output_json as real_final_output_json,
    generator_output_base as real_generator_output_base,
    prepare_generation_copies,
)
from i18n import tr


class SelectionApp:
    """Only the attributes the bound selection methods actually touch."""

    _add_json_paths = app_module.App._add_json_paths
    _load_existing_output_json_for_image = app_module.App._load_existing_output_json_for_image
    _queue_final_generation_output = app_module.App._queue_final_generation_output
    _run_one_generation = app_module.App._run_one_generation
    use_generated_outputs = app_module.App.use_generated_outputs

    def __init__(self):
        self.outputs = []
        self.json_files = []
        self.lang = "en"
        self.outputs_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.queued = []
        self.queue = types.SimpleNamespace(put=self.queued.append)
        self.logs = []

    def log_line(self, message):
        self.logs.append(message)

    def _render_lists(self):
        pass

    def log_messages(self):
        return [payload for kind, payload in self.queued if kind == "log"]


class FakeProc:
    """A generator process that has already exited with *returncode*."""

    def __init__(self, returncode=0):
        self.stdout = io.StringIO("")
        self.returncode = returncode
        self.pid = 4321

    def poll(self):
        return self.returncode


class StoppingProc:
    """A generator process whose first poll coincides with the stop request."""

    def __init__(self, event):
        self.stdout = io.StringIO("")
        self.returncode = 0
        self._event = event

    def poll(self):
        self._event.set()
        return None


def _make_image(tmp_path, name="mabynotimage.png"):
    path = tmp_path / "sources" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png-bytes")
    return path


def _patch_out_dir(monkeypatch, tmp_path):
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        app_module, "final_output_json", lambda image: real_final_output_json(image, out_dir)
    )
    monkeypatch.setattr(
        app_module, "generator_output_base", lambda image: real_generator_output_base(image, out_dir)
    )
    return out_dir


def run_generation(stub, tmp_path, monkeypatch, source, returncode=0, write_final=None, seed_final=None, stopping=False):
    out_dir = _patch_out_dir(monkeypatch, tmp_path)
    final = out_dir / "mabynotimage" / "png" / "mabynotimage.json"
    if seed_final is not None:
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_text(seed_final, encoding="utf-8")

    monkeypatch.setattr(app_module, "preprocess_input_image", lambda image, setting: image)
    monkeypatch.setattr(app_module, "generated_preview_files", lambda image: [])

    def fake_command(image, setting):
        if write_final is not None:
            final.parent.mkdir(parents=True, exist_ok=True)
            final.write_text(write_final, encoding="utf-8")
        return ["generator", str(image)]

    monkeypatch.setattr(app_module, "build_generator_command", fake_command)

    if stopping:
        proc = StoppingProc(stub.shutdown_event)
    else:
        proc = FakeProc(returncode)
    stub._popen_registered = lambda *args, **kwargs: proc
    stub._register_generator_proc = lambda proc: None
    stub._unregister_generator_proc = lambda proc: None
    stub._unregister_process = lambda proc: None
    stub._terminate_process = lambda proc: None
    stub._record_detail = lambda message: None
    stub._format_command = lambda cmd: " ".join(str(part) for part in cmd)
    stub.friendly_generator_line = lambda line: line
    stub.queue_generator_message = lambda friendly, last, prefix="", track_eta=True: None
    stub._generator_exit_message = lambda code: f"generator exit {code}"
    stub._prepare_generation_paths = lambda image_path: Path(image_path)

    outcome = stub._run_one_generation(source, {"path": tmp_path / "profile.ini"}, {})
    return outcome, final


class TestGenerationSuccessSelection:
    def test_success_queues_the_new_final_json(self, tmp_path, monkeypatch):
        source = _make_image(tmp_path)
        stub = SelectionApp()

        outcome, final = run_generation(stub, tmp_path, monkeypatch, source, write_final="{}")

        assert outcome == "done"
        assert stub.json_files == [final]
        assert stub.outputs == [final]
        assert any("Generated:" in message for message in stub.log_messages())

    def test_success_overwriting_an_existing_final_still_selects_it(self, tmp_path, monkeypatch):
        source = _make_image(tmp_path)
        stub = SelectionApp()

        outcome, final = run_generation(
            stub,
            tmp_path,
            monkeypatch,
            source,
            write_final='{"layers": 200, "note": "fresh run"}',
            seed_final='{"layers": 100}',
        )

        assert outcome == "done"
        assert stub.json_files == [final]

    def test_untouched_leftover_final_is_not_reported_as_output(self, tmp_path, monkeypatch):
        source = _make_image(tmp_path)
        stub = SelectionApp()

        outcome, final = run_generation(
            stub, tmp_path, monkeypatch, source, seed_final='{"layers": 100}'
        )

        assert outcome == "failed"
        assert stub.json_files == []
        assert final.exists()

    def test_failed_run_does_not_import_anything(self, tmp_path, monkeypatch):
        source = _make_image(tmp_path)
        stub = SelectionApp()

        outcome, _final = run_generation(
            stub, tmp_path, monkeypatch, source, returncode=1, write_final='{"layers": 5}'
        )

        assert outcome == "failed"
        assert stub.json_files == []
        assert tr("en", "checkpoint_manual_hint") in stub.log_messages()

    def test_stopped_run_does_not_import_anything(self, tmp_path, monkeypatch):
        source = _make_image(tmp_path)
        stub = SelectionApp()

        outcome, _final = run_generation(
            stub, tmp_path, monkeypatch, source, stopping=True, write_final='{"layers": 5}'
        )

        assert outcome == "stopped"
        assert stub.json_files == []
        assert tr("en", "checkpoint_manual_hint") in stub.log_messages()


class TestImportListSelection:
    def test_readd_auto_imports_only_the_final_json(self, tmp_path, monkeypatch):
        out_dir = _patch_out_dir(monkeypatch, tmp_path)
        source = _make_image(tmp_path)
        _backup, folder = prepare_generation_copies(source, tmp_path / "image", out_dir)
        (folder / "mabynotimage.json").write_text("{}", encoding="utf-8")
        (folder / "mabynotimage.500.json").write_text("{}", encoding="utf-8")
        stub = SelectionApp()

        added = stub._load_existing_output_json_for_image(source)

        assert added == 1
        assert stub.json_files == [out_dir / "mabynotimage" / "png" / "mabynotimage.json"]
        expected = tr("en", "existing_final_json_found").format(image=source.name)
        assert expected in stub.logs

    def test_readd_without_a_final_imports_nothing(self, tmp_path, monkeypatch):
        out_dir = _patch_out_dir(monkeypatch, tmp_path)
        source = _make_image(tmp_path)
        _backup, folder = prepare_generation_copies(source, tmp_path / "image", out_dir)
        (folder / "mabynotimage.500.json").write_text("{}", encoding="utf-8")
        stub = SelectionApp()

        assert stub._load_existing_output_json_for_image(source) == 0
        assert stub.json_files == []

    def test_use_generated_outputs_never_touches_manual_checkpoints(self, tmp_path):
        final = tmp_path / "out" / "mabynotimage" / "png" / "mabynotimage.json"
        final.parent.mkdir(parents=True)
        final.write_text("{}", encoding="utf-8")
        checkpoint = tmp_path / "manual" / "mabynotimage.500.json"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_text("{}", encoding="utf-8")
        stub = SelectionApp()
        stub.outputs = [final]
        stub.json_files = [checkpoint]

        stub.use_generated_outputs()

        assert stub.json_files == [checkpoint, final]

    def test_manual_add_still_accepts_checkpoints(self, tmp_path):
        checkpoint = tmp_path / "manual" / "mabynotimage.500.json"
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_text("{}", encoding="utf-8")
        stub = SelectionApp()

        assert stub._add_json_paths([checkpoint]) == 1
        assert stub.json_files == [checkpoint]
