"""Persist lightweight UI preferences (first-run flags, telemetry layout)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app_paths import ROOT

PREFERENCES_PATH = ROOT / "runtime" / "settings" / "ui_preferences.json"


def _default_preferences() -> Dict[str, Any]:
    return {
        "first_run_complete": False,
        "telemetry_compact": True,
        "write_workspace_signature": True,
        "text_import_shape_notice_dismissed": False,
        "generator_gpu_device": "",
    }


def load_ui_preferences() -> Dict[str, Any]:
    prefs = _default_preferences()
    try:
        if PREFERENCES_PATH.is_file():
            payload = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                prefs.update(payload)
    except (OSError, json.JSONDecodeError):
        pass
    prefs["first_run_complete"] = bool(prefs.get("first_run_complete"))
    prefs["telemetry_compact"] = bool(prefs.get("telemetry_compact", True))
    prefs["write_workspace_signature"] = bool(prefs.get("write_workspace_signature", True))
    prefs["text_import_shape_notice_dismissed"] = bool(prefs.get("text_import_shape_notice_dismissed"))
    prefs["generator_gpu_device"] = str(prefs.get("generator_gpu_device") or "")
    return prefs


def save_ui_preferences(prefs: Dict[str, Any]) -> None:
    try:
        PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        merged = _default_preferences()
        merged.update(prefs)
        PREFERENCES_PATH.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
