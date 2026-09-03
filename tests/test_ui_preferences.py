from __future__ import annotations

import json

import pytest

import ui_preferences
from ui_preferences import load_ui_preferences, save_ui_preferences


@pytest.fixture
def prefs_file(tmp_path, monkeypatch):
    path = tmp_path / "settings" / "ui_preferences.json"
    monkeypatch.setattr(ui_preferences, "PREFERENCES_PATH", path)
    return path


class TestDefaults:
    def test_missing_file_yields_defaults(self, prefs_file):
        prefs = load_ui_preferences()
        assert prefs["generator_gpu_device"] == ""
        assert prefs["generator_parallel_jobs"] == 1
        assert prefs["first_run_complete"] is False

    def test_unreadable_file_yields_defaults(self, prefs_file):
        prefs_file.parent.mkdir(parents=True)
        prefs_file.write_text("{ not json", encoding="utf-8")
        assert load_ui_preferences()["generator_parallel_jobs"] == 1


class TestGeneratorGpuDevice:
    def test_roundtrip(self, prefs_file):
        save_ui_preferences({"generator_gpu_device": "amd|Card|8192|32|0"})
        assert load_ui_preferences()["generator_gpu_device"] == "amd|Card|8192|32|0"

    def test_null_becomes_empty_string(self, prefs_file):
        prefs_file.parent.mkdir(parents=True)
        prefs_file.write_text(json.dumps({"generator_gpu_device": None}), encoding="utf-8")
        assert load_ui_preferences()["generator_gpu_device"] == ""


class TestGeneratorParallelJobs:
    def test_roundtrip(self, prefs_file):
        save_ui_preferences({"generator_parallel_jobs": 3})
        assert load_ui_preferences()["generator_parallel_jobs"] == 3

    def test_zero_and_negative_clamp_to_one(self, prefs_file):
        for stored in (0, -5):
            save_ui_preferences({"generator_parallel_jobs": stored})
            assert load_ui_preferences()["generator_parallel_jobs"] == 1

    def test_string_value_is_coerced(self, prefs_file):
        prefs_file.parent.mkdir(parents=True)
        prefs_file.write_text(json.dumps({"generator_parallel_jobs": "2"}), encoding="utf-8")
        assert load_ui_preferences()["generator_parallel_jobs"] == 2

    def test_garbage_value_falls_back_to_one(self, prefs_file):
        prefs_file.parent.mkdir(parents=True)
        prefs_file.write_text(json.dumps({"generator_parallel_jobs": "lots"}), encoding="utf-8")
        assert load_ui_preferences()["generator_parallel_jobs"] == 1

    def test_unknown_keys_survive_a_save(self, prefs_file):
        save_ui_preferences({"generator_parallel_jobs": 2, "future_setting": "keep me"})
        assert load_ui_preferences()["future_setting"] == "keep me"
