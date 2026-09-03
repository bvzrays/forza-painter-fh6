from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app_paths import RESOURCE_ROOT, ROOT
from geometry_json import drawable_shape_count
from utils import PreprocessError


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BUNDLED_SETTINGS_DIR = RESOURCE_ROOT / "config" / "settings"
USER_SETTINGS_DIR = ROOT / "config" / "settings"
SETTINGS_DIR = BUNDLED_SETTINGS_DIR
GENERATOR_EXE = RESOURCE_ROOT / "bin" / "forza-painter-geometrize-go.exe"
PREVIEW_DIR = ROOT / "runtime" / "previews"
CUSTOM_SETTINGS_DIR = ROOT / "runtime" / "custom-settings"

GENERATOR_PREVIEW_SCAN_SECONDS = 0.5
GENERATOR_JSON_SCAN_SECONDS = 2.0
GENERATOR_POLL_SLEEP_SECONDS = 0.2


# ---------------------------------------------------------------------------
# Setting keys
# ---------------------------------------------------------------------------

SETTING_KEYS: tuple[str, ...] = (
    "maxPreviewSize",
    "maxResolution",
    "maxThreads",
    "mutatedSamples",
    "enableProgressiveSampling",
    "progressiveSamplingStart",
    "progressiveSamplingEnd",
    "progressiveSamplingTransition",
    "progressiveSamplingCurve",
    "errorGridSize",
    "forceOpaqueShapes",
    "posterizeLevels",
    "previewEvery",
    "randomSamples",
    "preprocessMode",
    "saveAt",
    "saveEvery",
    "stopAt",
)

_GENERATOR_ENV_KEEP = {
    "ALLUSERSPROFILE",
    "APPDATA",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "COMMONPROGRAMW6432",
    "COMSPEC",
    "DRIVERDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER",
    "PROCESSOR_LEVEL",
    "PROCESSOR_REVISION",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "PUBLIC",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERDOMAIN",
    "USERNAME",
    "USERPROFILE",
    "WINDIR",
}

_GENERATOR_ENV_DROP_PREFIXES = (
    "CONDA",
    "CUDA_VISIBLE_DEVICES",
    "OCL_ICD",
    "OPENCL",
    "PYTHON",
    "PYENV",
    "VIRTUAL_ENV",
    "VK_",
    "VULKAN",
)

_PATH_DROP_FRAGMENTS = (
    "\\.venv",
    "/.venv",
    "\\venv\\",
    "/venv/",
    "anaconda",
    "conda",
    "miniconda",
    "python",
    "stable-diffusion",
    "webui",
)


def _filtered_path(value):
    kept = []
    seen = set()
    for entry in str(value or "").split(os.pathsep):
        item = entry.strip()
        if not item:
            continue
        lowered = item.lower()
        if any(fragment in lowered for fragment in _PATH_DROP_FRAGMENTS):
            continue
        key = lowered.rstrip("\\/")
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return os.pathsep.join(kept)


def build_generator_env(extra_env: dict[str, str] | None = None):
    """Build the sanitized generator environment.

    *extra_env* is applied after sanitizing, so deliberate overrides such as the
    GPU device ordinals from :mod:`gpu_devices` survive the drop list.
    """
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper not in _GENERATOR_ENV_KEEP:
            continue
        if upper == "PATH":
            env[key] = _filtered_path(value)
        else:
            env[key] = value
    for key in list(env):
        upper = key.upper()
        if any(upper.startswith(prefix) for prefix in _GENERATOR_ENV_DROP_PREFIXES):
            env.pop(key, None)
    for key, value in (extra_env or {}).items():
        env[str(key)] = str(value)
    env["FORZA_PAINTER_GENERATOR_SANITIZED_ENV"] = "1"
    return env


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SettingProfile:
    """Represents a single settings preset (bundled or user).

    Supports both attribute access (``.path``) and dict-style access
    (``setting['path']``) for backward compatibility with legacy UI code.
    """

    index: int
    source: str
    path: Path
    label: str
    description: str = ""
    values: dict[str, str] = field(default_factory=dict)

    def __getitem__(self, key: str):
        # AttributeError → KeyError for dict-style backward compat.
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


# ---------------------------------------------------------------------------
# Settings parsing
# ---------------------------------------------------------------------------

def setting_description(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("description"):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def parse_settings(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def merged_settings_values(
    base_setting: SettingProfile, custom_values: dict[str, str]
) -> dict[str, str]:
    values = dict(parse_settings(base_setting.path))
    for key, value in custom_values.items():
        value = str(value).strip()
        if value:
            values[key] = value
    return values


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

def _settings_paths() -> Iterable[tuple[str, Path]]:
    seen: set[str] = set()
    for source, folder in (
        ("bundled", BUNDLED_SETTINGS_DIR),
        ("user", USER_SETTINGS_DIR),
    ):
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.ini")):
            if path.name.startswith("_"):
                continue
            try:
                key = str(path.resolve()).lower()
            except OSError:
                key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            yield source, path


def load_settings() -> list[SettingProfile]:
    profiles: list[SettingProfile] = []
    for index, (source, path) in enumerate(_settings_paths(), start=1):
        name = re.sub(r"^[a-z0-9]+[.)]\s*", "", path.stem, flags=re.IGNORECASE)
        name = name.replace(" - ", " / ")
        if source == "user":
            name = f"User / {name}"
        profiles.append(
            SettingProfile(
                index=index,
                source=source,
                path=path,
                label=f"{index}. {name}",
                description=setting_description(path),
                values=parse_settings(path),
            )
        )
    return profiles


def write_custom_settings(
    base_setting: SettingProfile, custom_values: dict[str, str]
) -> SettingProfile:
    values = merged_settings_values(base_setting, custom_values)
    CUSTOM_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = CUSTOM_SETTINGS_DIR / "custom.ini"
    lines = ["description = Custom UI settings"]
    for key in SETTING_KEYS:
        if key in values:
            lines.append(f"{key} = {values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return SettingProfile(
        index=base_setting.index,
        source="custom",
        path=path,
        label="Custom",
        description="Custom UI settings",
        values=values,
    )


def write_user_settings_preset(
    base_setting: SettingProfile,
    custom_values: dict[str, str],
    output_path: str | Path,
    description: str = "User custom settings",
) -> Path:
    values = merged_settings_values(base_setting, custom_values)
    USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(output_path)
    if path.suffix.lower() != ".ini":
        path = path.with_suffix(".ini")
    lines = [f"description = {description}"]
    for key in SETTING_KEYS:
        if key in values:
            lines.append(f"{key} = {values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def _get_preprocess_mode(values: dict[str, str] | None) -> str | None:
    if not values:
        return None
    mode = str(values.get("preprocessMode", "")).strip().lower()
    if mode == "none" or not mode:
        return None
    return mode


def _preprocessed_image_path(image_path: Path, mode: str) -> Path:
    return image_path.with_name(f"{image_path.stem}.{mode}{image_path.suffix}")


def preprocess_input_image(
    image_path: str | Path, setting: SettingProfile
) -> Path:
    image_path = Path(image_path)
    mode = _get_preprocess_mode(setting.values)
    if mode is None:
        return image_path

    output_path = _preprocessed_image_path(image_path, mode)
    try:
        if (
            output_path.exists()
            and output_path.stat().st_mtime >= image_path.stat().st_mtime
        ):
            return output_path
    except OSError:
        pass

    if mode == "luma_band":
        # Delayed import to avoid circular deps at module load time.
        luma_band = __import__("preprocess.luma", fromlist=["luma_band"]).luma_band
        return luma_band(image_path)
    raise PreprocessError(f"unsupported preprocess mode: {mode}")


# ---------------------------------------------------------------------------
# Output discovery
# ---------------------------------------------------------------------------

def generated_jsons(image_path: str | Path) -> list[Path]:
    image_path = Path(image_path)
    candidates: list[Path] = []
    output_base = generator_output_base(image_path)
    folders = {
        image_path.parent / image_path.stem,
        output_base.parent / output_base.name,
    }
    for folder in folders:
        if folder.exists():
            candidates.extend(folder.rglob("*.json"))
    prefixes = {
        image_path.stem,
        image_path.name,
        output_base.name,
        image_path.stem.split(".", 1)[0],
        output_base.name.split(".", 1)[0],
    }
    patterns = {f"{prefix}*.json" for prefix in prefixes if prefix}
    for pattern in patterns:
        candidates.extend(image_path.parent.glob(pattern))
        if output_base.parent != image_path.parent:
            candidates.extend(output_base.parent.glob(pattern))
    return sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)


def geometry_shape_count(path: str | Path) -> int:
    return drawable_shape_count(path)


def best_geometry_jsons(paths: Iterable[str | Path]) -> list[Path]:
    best_by_stem: dict[str, tuple[tuple[int, float], Path]] = {}
    for path in paths:
        path = Path(path)
        base_name = re.sub(r"\.\d+$", "", path.stem)
        key = str(path.with_name(base_name).resolve()).lower()
        score = (geometry_shape_count(path), path.stat().st_mtime)
        current = best_by_stem.get(key)
        if current is None or score > current[0]:
            best_by_stem[key] = (score, path)
    return [
        item[1]
        for item in sorted(
            best_by_stem.values(), key=lambda item: item[1].stat().st_mtime, reverse=True
        )
    ]


# ---------------------------------------------------------------------------
# Preview / output helpers
# ---------------------------------------------------------------------------

def generator_preview_path(image_path: str | Path) -> Path:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    image_path = Path(image_path)
    return PREVIEW_DIR / f"{_name_without_suffix(image_path)}.preview.png"


def generated_preview_files(image_path: str | Path) -> list[Path]:
    image_path = Path(image_path)
    if not PREVIEW_DIR.exists():
        return []
    stem = _name_without_suffix(image_path)
    return sorted(
        PREVIEW_DIR.glob(f"{stem}.preview*.png"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def generator_output_base(image_path: str | Path) -> Path:
    image_path = Path(image_path)
    return image_path.with_name(_name_without_suffix(image_path))


def _name_without_suffix(path: Path) -> str:
    return path.stem


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------

def build_generator_command(
    image_path: str | Path, setting: SettingProfile
) -> list[str]:
    image_path = Path(image_path)
    return [
        str(GENERATOR_EXE),
        str(image_path),
        "-settings",
        str(setting.path),
        "-output",
        str(generator_output_base(image_path)),
        "-preview",
        str(generator_preview_path(image_path)),
    ]
