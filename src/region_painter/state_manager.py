"""Workflow state persistence for region-focused iterative painting.

Persists workflow progress to a ``state.json`` file so that multi-pass
generation can be paused and resumed across application restarts.
"""

from __future__ import annotations

import json
from pathlib import Path


class StateManager:
    """Manages the lifecycle of a single region-paint workflow.

    All persisted data lives under ``{work_dir}/state.json``.
    """

    def __init__(self, work_dir: str | Path) -> None:
        self._work_dir = Path(work_dir)
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self._work_dir / "state.json"
        self._data: dict = {}
        self.load()

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def load(self) -> dict:
        """Load state from disk, or return an empty default."""
        if self._state_path.exists():
            try:
                self._data = json.loads(self._state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}
        self._ensure_defaults()
        return self._data

    def save(self) -> None:
        """Persist current state to disk atomically."""
        text = json.dumps(self._data, indent=2, ensure_ascii=False)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self._state_path)

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def init_first_pass(
        self,
        original_image: str,
        original_ini: str,
        total_budget: int,
        working_width: int,
        working_height: int,
        max_resolution: int,
        max_preview_size: int,
    ) -> None:
        """Set up a fresh workflow before the first pass runs."""
        self._data = {
            "original_image": str(original_image),
            "original_ini": str(original_ini),
            "total_budget": total_budget,
            "used_layers": 0,
            "working_width": working_width,
            "working_height": working_height,
            "max_resolution": max_resolution,
            "max_preview_size": max_preview_size,
            "base_json": "",
            "target_path": "",
            "preview_path": "",
            "passes": [],
            "active_checkpoint_index": 0,
            "checkpoint_counter": {},
        }
        self.save()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_budget(self) -> int:
        return int(self._data.get("total_budget", 0))

    @property
    def used_layers(self) -> int:
        """Layers used up to the active checkpoint (inclusive)."""
        active = self.active_checkpoint_index
        passes = self._data.get("passes", [])
        if active < 0 or not passes:
            return 0
        # Sum layers from pass 0 up to and including active_checkpoint_index
        total = 0
        for i, p in enumerate(passes):
            if i > active:
                break
            total += p.get("layers", 0)
        return total

    @property
    def remaining_budget(self) -> int:
        return max(0, self.total_budget - self.used_layers)

    @property
    def is_first_pass_done(self) -> bool:
        return self.used_layers > 0 and len(self._data.get("passes", [])) >= 1

    @property
    def active_checkpoint_index(self) -> int:
        return int(self._data.get("active_checkpoint_index", -1))

    @active_checkpoint_index.setter
    def active_checkpoint_index(self, value: int) -> None:
        self._data["active_checkpoint_index"] = int(value)

    @property
    def checkpoint_counter(self) -> dict:
        return dict(self._data.get("checkpoint_counter", {}))

    @property
    def working_width(self) -> int:
        return int(self._data.get("working_width", 0))

    @property
    def working_height(self) -> int:
        return int(self._data.get("working_height", 0))

    @property
    def max_resolution(self) -> int:
        return int(self._data.get("max_resolution", 1200))

    @property
    def max_preview_size(self) -> int:
        return int(self._data.get("max_preview_size", 500))

    @property
    def target_path(self) -> str:
        return str(self._data.get("target_path", ""))

    @target_path.setter
    def target_path(self, value: str) -> None:
        self._data["target_path"] = str(value)

    @property
    def base_json(self) -> str:
        return str(self._data.get("base_json", ""))

    @base_json.setter
    def base_json(self, value: str) -> None:
        self._data["base_json"] = str(value)

    @property
    def preview_path(self) -> str:
        return str(self._data.get("preview_path", ""))

    @preview_path.setter
    def preview_path(self, value: str) -> None:
        self._data["preview_path"] = str(value)

    @property
    def passes(self) -> list[dict]:
        return list(self._data.get("passes", []))

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_pass(
        self,
        mask_path: str | None,
        layers: int,
        json_path: str,
        pass_num: int | None = None,
        attempt: int | None = None,
        preview_path: str = "",
        heatmap_path: str = "",
    ) -> None:
        """Record a completed generation pass (checkpoint).

        Args:
            mask_path: Path to the mask PNG used (None for first pass).
            layers: Number of layers added in this pass.
            json_path: Path to the checkpoint JSON file.
            pass_num: Logical pass number (1 = first pass, 2 = first region, etc.).
            attempt: Attempt number for this pass_num (1, 2, ... after rollbacks).
            preview_path: Path to checkpoint-specific preview PNG.
            heatmap_path: Path to checkpoint-specific heatmap PNG.
        """
        import datetime as _dt
        passes = self._data.setdefault("passes", [])
        actual_pass_num = pass_num if pass_num is not None else len(passes) + 1
        actual_attempt = attempt if attempt is not None else 1
        entry: dict = {
            "pass_num": actual_pass_num,
            "attempt": actual_attempt,
            "mask": str(mask_path) if mask_path else None,
            "layers": layers,
            "json": str(json_path),
            "preview": str(preview_path) if preview_path else "",
            "heatmap": str(heatmap_path) if heatmap_path else "",
            "timestamp": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        passes.append(entry)
        # Set active checkpoint to the newly added pass
        self._data["active_checkpoint_index"] = len(passes) - 1
        # Recompute used_layers up to active checkpoint
        self._data["used_layers"] = self.used_layers
        self.save()

    def get_checkpoints(self) -> list[dict]:
        """Return all checkpoint entries with metadata for UI display."""
        return list(self._data.get("passes", []))

    def restore_to_checkpoint(self, index: int) -> dict:
        """Roll back to a specific checkpoint by its index in the passes array.

        Sets active_checkpoint_index, updates base_json to point to the
        checkpoint's JSON file, and recomputes used_layers.
        Returns the checkpoint entry dict.
        """
        passes = self._data.get("passes", [])
        if index < 0 or index >= len(passes):
            raise IndexError(f"Checkpoint index {index} out of range (0-{len(passes) - 1})")
        entry = passes[index]
        self._data["active_checkpoint_index"] = index
        self._data["base_json"] = str(entry.get("json", ""))
        self._data["used_layers"] = self.used_layers
        self.save()
        return dict(entry)

    def next_attempt(self, pass_num: int) -> int:
        """Return the next attempt number for the given pass_num, and increment.

        Called when starting a new pass. If the user has already run pass N
        once and is re-running it after a rollback, this returns 2 (or higher).
        """
        counter = self._data.setdefault("checkpoint_counter", {})
        key = str(pass_num)
        current = counter.get(key, 0)
        next_val = current + 1
        counter[key] = next_val
        # Also update _data directly since we modified the nested dict
        self._data["checkpoint_counter"] = counter
        # Don't save here — caller will save after add_pass()
        return next_val

    def reset(self) -> None:
        """Clear all state for a fresh workflow."""
        self._data = {}
        self._ensure_defaults()
        if self._state_path.exists():
            try:
                self._state_path.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_defaults(self) -> None:
        self._data.setdefault("total_budget", 0)
        self._data.setdefault("used_layers", 0)
        self._data.setdefault("working_width", 0)
        self._data.setdefault("working_height", 0)
        self._data.setdefault("max_resolution", 1200)
        self._data.setdefault("max_preview_size", 500)
        self._data.setdefault("original_image", "")
        self._data.setdefault("original_ini", "")
        self._data.setdefault("base_json", "")
        self._data.setdefault("target_path", "")
        self._data.setdefault("preview_path", "")
        self._data.setdefault("passes", [])
        self._data.setdefault("active_checkpoint_index", -1)
        self._data.setdefault("checkpoint_counter", {})
