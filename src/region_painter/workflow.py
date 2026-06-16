"""Core orchestration for region-focused iterative painting.

Setup-only functions that prepare files and return commands.
The actual subprocess management (Popen, stdout streaming, file polling)
happens in app.py worker threads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image

from generator_backend import GENERATOR_EXE, parse_settings
from region_painter.ini_manager import modify_ini
from region_painter.preview_renderer import (
    load_shapes_from_json,
    prune_shapes_for_region,
    render_preview,
    render_preview_high_quality,
    render_shapes_to_array,
)
from region_painter.state_manager import StateManager

# Lazy-loaded via utils.load_cv2 in the composite path.
_np = None
_cv2 = None

ProgressCallback = Callable[[str], None]


def prepare_first_pass(
    image_path, settings_path, first_layers, output_dir,
    exe_path="", on_progress=None,
):
    """Prepare first pass. Returns dict with cmd, paths, state. Does NOT run exe."""
    image_path = Path(image_path).resolve()
    settings_path = Path(settings_path).resolve()
    output_dir = Path(output_dir)
    exe = Path(exe_path) if exe_path else Path(str(GENERATOR_EXE))
    if not exe.exists():
        return {"error": f"Generator exe not found: {exe}"}
    values = parse_settings(settings_path)
    total_budget = int(values.get("stopAt", 3000))
    max_resolution = int(values.get("maxResolution", 1200))
    max_preview_size = int(values.get("maxPreviewSize", 500))
    first_layers = min(first_layers, total_budget)
    _p(on_progress, f"Total budget: {total_budget}, first pass: {first_layers}")
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_ini = output_dir / "temp.ini"
    base_json = output_dir / "base.json"
    preview_png = output_dir / "preview.png"
    target_png = output_dir / "target.png"
    img = Image.open(image_path).convert("RGBA")
    orig_w, orig_h = img.size
    if max(orig_w, orig_h) > max_resolution:
        ratio = max_resolution / max(orig_w, orig_h)
        img = img.resize((max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio))), Image.LANCZOS)
    working_w, working_h = img.size
    img.save(target_png, "PNG")
    modify_ini(settings_path, temp_ini, stop_at=first_layers)
    state = StateManager(output_dir)
    state.init_first_pass(
        original_image=str(image_path), original_ini=str(settings_path),
        total_budget=total_budget, working_width=working_w, working_height=working_h,
        max_resolution=max_resolution, max_preview_size=max_preview_size,
    )
    state.target_path = str(target_png)
    state.base_json = str(base_json)
    state.preview_path = str(preview_png)
    cmd = [str(exe), str(target_png), "-settings", str(temp_ini),
           "-output", str(base_json.with_suffix("")),
           "-preview", str(output_dir / "_exe_preview")]
    _p(on_progress, f"Command: {cmd[0]} ...")
    return {"cmd": cmd, "output_dir": str(output_dir), "target_png": str(target_png),
            "preview_png": str(preview_png), "base_json": str(base_json),
            "total_budget": total_budget, "max_preview_size": max_preview_size, "state": state}


def finalize_first_pass(prep):
    """Post-process after first-pass exe finishes.

    Saves the result as base.json AND as an independent checkpoint so
    the user can later roll back to this exact state.
    """
    import shutil

    output_dir = Path(prep["output_dir"])
    base_json = Path(prep["base_json"])
    target_png = Path(prep["target_png"])
    preview_png = Path(prep["preview_png"])
    max_preview_size = prep.get("max_preview_size", 500)
    state = prep["state"]
    json_files = sorted(output_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not json_files:
        return {"ok": False, "error": "No JSON output found after generation."}
    actual_json = json_files[0]
    if actual_json != base_json:
        shutil.copy2(actual_json, base_json)
    shapes = load_shapes_from_json(base_json)
    layers = max(0, len(shapes) - 1)
    try:
        render_preview_high_quality(target_png, shapes, preview_png, max_preview_size)
    except Exception:
        pass
    state.base_json = str(base_json)

    # --- Save independent checkpoint ---
    checkpoints_dir = output_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    pass_num = 1
    attempt = state.next_attempt(pass_num)
    ckpt_json = checkpoints_dir / f"pass{pass_num}_attempt{attempt}.json"
    ckpt_preview = checkpoints_dir / f"pass{pass_num}_attempt{attempt}_preview.png"
    ckpt_heatmap = checkpoints_dir / f"pass{pass_num}_attempt{attempt}_heatmap.png"
    shutil.copy2(base_json, ckpt_json)
    if preview_png.exists():
        shutil.copy2(preview_png, ckpt_preview)
    # Generate heatmap for checkpoint
    try:
        from scripts.heatmap import generate_standalone_heatmap
        generate_standalone_heatmap(base_json, ckpt_heatmap)
    except Exception:
        pass

    state.add_pass(
        mask_path=None, layers=layers,
        json_path=str(ckpt_json),
        pass_num=pass_num, attempt=attempt,
        preview_path=str(ckpt_preview),
        heatmap_path=str(ckpt_heatmap),
    )
    return {"ok": True, "layers": layers, "preview_png": str(preview_png),
            "checkpoint_json": str(ckpt_json),
            "checkpoint_preview": str(ckpt_preview),
            "checkpoint_heatmap": str(ckpt_heatmap)}


def prepare_region_pass(
    output_dir, region_layers, selection_mask,
    exe_path="", on_progress=None,
):
    """Prepare region pass. Returns dict with cmd, paths, state. Does NOT run exe."""
    output_dir = Path(output_dir)
    exe = Path(exe_path) if exe_path else Path(str(GENERATOR_EXE))
    if not exe.exists():
        return {"error": f"Generator exe not found: {exe}"}
    state = StateManager(output_dir)
    if not state.is_first_pass_done:
        return {"error": "First pass has not been completed."}
    if region_layers > state.remaining_budget:
        region_layers = state.remaining_budget
    if region_layers <= 0:
        return {"error": "No remaining budget for region pass."}
    # stopAt must be > len(shapes) for -resume to work (exe validates this).
    new_stop_at = state.used_layers + region_layers
    target_png = Path(state.target_path)
    pass_n = len(state.passes) + 1
    region_target = output_dir / f"region_target_pass{pass_n}.png"
    # --- Prune shapes → masked target → resume from pruned ---
    # 1. Prune shapes: keep those inside the mask; delete those outside.
    # 2. Use transparent-masked target (exe only generates in mask region).
    # 3. Resume from pruned json so exe only sees surviving shapes.
    # 4. stopAt = num_pruned_type16 + region_layers.
    base_json = Path(state.base_json)
    all_shapes = load_shapes_from_json(base_json) if base_json.exists() else []
    if not all_shapes:
        return {"error": "No accumulated shapes found."}
    bg_data = all_shapes[0].get("data", [])
    if len(bg_data) < 4:
        return {"error": "Invalid background shape."}
    working_w = int(bg_data[2])
    working_h = int(bg_data[3])

    # Prune shapes against the selection mask.
    pruned, num_pruned = prune_shapes_for_region(
        all_shapes, selection_mask, working_w, working_h,
    )
    new_stop_at = num_pruned + region_layers

    # Save pruned shapes as the resume checkpoint.
    pruned_json = output_dir / f"pruned_pass{pass_n}.json"
    import json as _json
    pruned_json.write_text(
        _json.dumps({"shapes": pruned}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Build masked target (transparent outside selection).
    try:
        from region_painter.image_processor import apply_selection_mask
        apply_selection_mask(target_png, selection_mask, region_target, feather_radius=0)
    except Exception as exc:
        return {"error": f"Failed to apply selection mask: {exc}"}

    mask_png = output_dir / f"pass_{pass_n}_mask.png"
    selection_mask.save(mask_png, "PNG")
    settings_path = Path(state._data.get("original_ini", ""))
    temp_ini = output_dir / "temp.ini"
    if not settings_path.exists():
        return {"error": f"Original settings INI not found: {settings_path}"}
    # Filter saveAt to only include values >= used_layers so the exe
    # does not emit spurious checkpoints during occlusion-culling
    # compaction (where the shape count temporarily drops).
    settings_values = parse_settings(settings_path)
    orig_save_at_str = settings_values.get("saveAt", "")
    orig_save_at = []
    for p in orig_save_at_str.split(","):
        try:
            orig_save_at.append(int(p.strip()))
        except ValueError:
            pass
    used = state.used_layers
    filtered_save_at = [v for v in orig_save_at if v >= used]
    modify_ini(settings_path, temp_ini, stop_at=new_stop_at, save_at=filtered_save_at)
    # Back up the FULL original shapes (pre-pruning) for final merge.
    backup_json = output_dir / "_base_backup.json"
    import shutil
    shutil.copy2(base_json, backup_json)

    cmd = [str(exe), str(region_target), "-resume", str(pruned_json),
           "-settings", str(temp_ini),
           "-preview", str(output_dir / "_exe_preview")]
    _p(on_progress, f"Region pass: {region_layers} layers (pruned={num_pruned}, stopAt={new_stop_at}, remaining={state.remaining_budget})")
    return {"cmd": cmd, "output_dir": str(output_dir), "target_png": str(target_png),
            "preview_png": state.preview_path, "base_json": str(base_json),
            "backup_json": str(backup_json), "pruned_json": str(pruned_json),
            "mask_png": str(mask_png), "new_stop_at": new_stop_at,
            "region_layers": region_layers, "state": state,
            "region_target_stem": region_target.stem,
            "max_preview_size": state.max_preview_size,
            "num_pruned": num_pruned}


def finalize_region_pass(prep):
    """Post-process after region-pass exe finishes.

    The exe ran with: pruned shapes → generated *region_layers* new shapes.
    We extract the new shapes (last region_layers type-16 from the exe
    output), merge them with the original full backup, and save.

    Saves the merged result as base.json AND as an independent checkpoint
    so the user can later roll back to this exact state.
    """
    import json
    import shutil
    import time

    _t0 = time.time()

    state = prep["state"]
    output_dir = Path(prep["output_dir"])
    base_json = Path(prep["base_json"])
    backup_json = Path(prep["backup_json"])
    target_png = Path(prep["target_png"])
    preview_png = Path(prep["preview_png"])
    mask_png = prep.get("mask_png", "")
    max_preview_size = prep.get("max_preview_size", 500)
    region_target_stem = prep.get("region_target_stem", "")
    region_layers = prep.get("region_layers", 0)
    num_pruned = prep.get("num_pruned", 0)

    # Load original full shapes from backup.
    _t = time.time()
    original = load_shapes_from_json(backup_json) if backup_json.exists() else []
    print(f"[finalize_region_pass] load backup shapes: {time.time() - _t:.3f}s ({len(original)} shapes)")

    # Find the exe's output (pruned shapes + new shapes).
    _t = time.time()
    exe_output: list[dict] = []
    if region_target_stem:
        for c in sorted(
            output_dir.glob(f"{region_target_stem}*.json"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        ):
            if c == backup_json:
                continue
            try:
                exe_output = load_shapes_from_json(c)
                break
            except Exception:
                pass

    if not exe_output:
        exe_output = original  # fallback
    print(f"[finalize_region_pass] find exe output: {time.time() - _t:.3f}s ({len(exe_output)} shapes)")

    # Extract new shapes: shapes at the end beyond the pruned count.
    _t = time.time()
    exe_type16 = [s for s in exe_output if s.get("type") == 16]
    new_type16 = exe_type16[num_pruned:num_pruned + region_layers]
    print(f"[finalize_region_pass] extract new shapes: {time.time() - _t:.3f}s "
          f"(exe_type16={len(exe_type16)}, new_type16={len(new_type16)})")

    # Merge: original full shapes + extracted new shapes.
    _t = time.time()
    bg = original[0] if original else exe_output[0]
    original_type16 = [s for s in original if s.get("type") == 16]
    merged_type16 = original_type16 + new_type16
    merged = [bg] + merged_type16
    print(f"[finalize_region_pass] merge shapes: {time.time() - _t:.3f}s "
          f"(total={len(merged)}, type16={len(merged_type16)})")

    new_layers = len(new_type16)
    if new_layers == 0:
        new_layers = region_layers

    # Save merged result to base.json (active state).
    _t = time.time()
    base_json.write_text(
        json.dumps({"shapes": merged}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[finalize_region_pass] save merged json: {time.time() - _t:.3f}s")

    # Render preview for active state.
    _t = time.time()
    try:
        render_preview_high_quality(target_png, merged, preview_png, max_preview_size)
    except Exception:
        pass
    print(f"[finalize_region_pass] render preview: {time.time() - _t:.3f}s")

    # --- Save independent checkpoint ---
    checkpoints_dir = output_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    # pass_n = number of completed passes + 1 (the one we just finished)
    pass_num = len(state.passes) + 1
    attempt = state.next_attempt(pass_num)
    ckpt_json = checkpoints_dir / f"pass{pass_num}_attempt{attempt}.json"
    ckpt_preview = checkpoints_dir / f"pass{pass_num}_attempt{attempt}_preview.png"
    ckpt_heatmap = checkpoints_dir / f"pass{pass_num}_attempt{attempt}_heatmap.png"
    shutil.copy2(base_json, ckpt_json)
    if preview_png.exists():
        shutil.copy2(preview_png, ckpt_preview)
    # Generate heatmap for checkpoint
    try:
        from scripts.heatmap import generate_standalone_heatmap
        generate_standalone_heatmap(base_json, ckpt_heatmap)
    except Exception:
        pass
    print(f"[finalize_region_pass] checkpoint saved: {ckpt_json}")

    state.add_pass(
        mask_path=str(mask_png), layers=new_layers,
        json_path=str(ckpt_json),
        pass_num=pass_num, attempt=attempt,
        preview_path=str(ckpt_preview),
        heatmap_path=str(ckpt_heatmap),
    )
    print(f"[finalize_region_pass] state.add_pass: {time.time() - _t:.3f}s")

    # Keep _base_backup.json for potential future rollbacks.
    # Only clean up the pruned JSON (temporary file).
    pruned_json = Path(prep.get("pruned_json", ""))
    try:
        pruned_json.unlink()
    except (OSError, TypeError):
        pass
    print(f"[finalize_region_pass] cleanup: {time.time() - _t:.3f}s")

    print(f"[finalize_region_pass] TOTAL: {time.time() - _t0:.3f}s")
    return {"ok": True, "new_total": len(merged_type16), "preview_png": str(preview_png),
            "checkpoint_json": str(ckpt_json),
            "checkpoint_preview": str(ckpt_preview),
            "checkpoint_heatmap": str(ckpt_heatmap)}


def get_status(output_dir):
    """Return a summary of the current workflow state."""
    state = StateManager(output_dir)
    return {
        "total_budget": state.total_budget,
        "used_layers": state.used_layers,
        "remaining": state.remaining_budget,
        "passes": state.passes,
        "is_first_pass_done": state.is_first_pass_done,
        "active_checkpoint_index": state.active_checkpoint_index,
    }


def restore_checkpoint(output_dir, checkpoint_index: int):
    """Roll back to a specific checkpoint.

    Copies the checkpoint JSON to base.json, re-renders preview and
    heatmap for the active state. Returns dict with paths for UI refresh.
    """
    import shutil
    output_dir = Path(output_dir)
    state = StateManager(output_dir)
    entry = state.restore_to_checkpoint(checkpoint_index)

    ckpt_json = Path(entry["json"])
    base_json = output_dir / "base.json"
    if ckpt_json.exists() and ckpt_json != base_json:
        shutil.copy2(ckpt_json, base_json)

    # Re-render preview
    target_png = Path(state.target_path)
    preview_png = output_dir / "preview.png"
    if target_png.exists() and base_json.exists():
        shapes = load_shapes_from_json(base_json)
        try:
            render_preview_high_quality(target_png, shapes, preview_png, state.max_preview_size)
        except Exception:
            pass

    # Re-render heatmap
    heatmap_png = output_dir / "heatmap.png"
    if base_json.exists():
        try:
            from scripts.heatmap import generate_standalone_heatmap
            generate_standalone_heatmap(base_json, heatmap_png)
        except Exception:
            pass

    return {
        "ok": True,
        "preview_png": str(preview_png) if preview_png.exists() else "",
        "heatmap_png": str(heatmap_png) if heatmap_png.exists() else "",
        "checkpoint": entry,
    }


def finalize(output_dir, dest_path):
    """Copy the final JSON to dest_path."""
    import shutil
    output_dir = Path(output_dir)
    dest_path = Path(dest_path)
    state = StateManager(output_dir)
    base_json = Path(state.base_json)
    if not base_json.exists():
        return {"ok": False, "error": f"Base JSON not found: {base_json}"}
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(base_json, dest_path)
    return {"ok": True, "output": str(dest_path)}


def _p(callback, msg):
    if callback:
        callback(msg)
