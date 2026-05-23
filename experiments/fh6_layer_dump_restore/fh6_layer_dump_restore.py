import argparse
import base64
import json
import struct
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import psutil


EXPERIMENT_DIR = Path(__file__).resolve().parent
ROOT = EXPERIMENT_DIR.parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


FORMAT_NAME = "fh6_layer_raw_dump_v1"
DEFAULT_BLOB_SIZE = 0x140
KNOWN_FIELD_SPECS = (
    ("position", "layer_position_offset", 8),
    ("scale", "layer_scale_offset", 8),
    ("rotation", "layer_rotation_offset", 4),
    ("color", "layer_color_offset", 4),
    ("mask", "layer_mask_offset", 1),
    ("shape_id_byte", "layer_shape_id_offset", 1),
)
SHAPE_FIELD_SPECS = (
    ("shape_vertex_count", 0x58, 4),
    ("shape_id_byte", 0x7A, 1),
    ("shape_resource_pointer", 0xA8, 8),
)

_FH6_MODULES = None


def fh6_modules():
    global _FH6_MODULES
    if _FH6_MODULES is None:
        from fh6_probe import auto_locate_count_table
        from game_profiles import get_profile
        from native import dereference_pointer, read_process_memory, write_process_memory

        _FH6_MODULES = {
            "auto_locate_count_table": auto_locate_count_table,
            "get_profile": get_profile,
            "dereference_pointer": dereference_pointer,
            "read_process_memory": read_process_memory,
            "write_process_memory": write_process_memory,
        }
    return _FH6_MODULES


def parse_int(value):
    if value is None:
        return None
    return int(str(value), 0)


def find_pid(profile):
    names = {name.lower() for name in profile.process_names}
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if (proc.info.get("name") or "").lower() in names:
                return int(proc.info["pid"])
        except psutil.Error:
            continue
    raise RuntimeError(f"No running process found for {profile.label}.")


def locate_session(pid, profile, layer_count, max_seconds):
    auto_locate_count_table = fh6_modules()["auto_locate_count_table"]
    session = auto_locate_count_table(
        pid=pid,
        profile=profile,
        layer_count=layer_count,
        limit_mb=2048,
        max_matches=500000,
        progress_every=0,
        radius=0x800,
        output_path=None,
        max_seconds=max_seconds,
    )
    if not session:
        raise RuntimeError("No safe FH6 layer table was located.")
    return session


def unpack_float_pair(raw, offset):
    if offset + 8 > len(raw):
        return None
    return list(struct.unpack_from("<ff", raw, offset))


def unpack_float(raw, offset):
    if offset + 4 > len(raw):
        return None
    return struct.unpack_from("<f", raw, offset)[0]


def summarize_blob(raw, profile):
    color_offset = profile.layer_color_offset
    mask_offset = profile.layer_mask_offset
    shape_offset = profile.layer_shape_id_offset
    color = list(raw[color_offset:color_offset + 4]) if color_offset + 4 <= len(raw) else None
    return {
        "position": unpack_float_pair(raw, profile.layer_position_offset),
        "scale": unpack_float_pair(raw, profile.layer_scale_offset),
        "rotation": unpack_float(raw, profile.layer_rotation_offset),
        "color": color,
        "mask": raw[mask_offset] if mask_offset < len(raw) else None,
        "shape_id_byte": raw[shape_offset] if shape_offset < len(raw) else None,
        "crc32": f"{zlib.crc32(raw) & 0xFFFFFFFF:08x}",
    }


def iter_layer_pointers(pid, table_address, layer_count):
    dereference_pointer = fh6_modules()["dereference_pointer"]
    for index in range(layer_count):
        pointer = dereference_pointer(pid, table_address + index * 8)
        yield index, pointer


def export_dump(args):
    modules = fh6_modules()
    get_profile = modules["get_profile"]
    read_process_memory = modules["read_process_memory"]

    profile = get_profile(args.game)
    pid = args.pid or find_pid(profile)
    layer_count = int(args.layer_count)
    blob_size = parse_int(args.blob_size)
    max_layers = int(args.max_layers) if args.max_layers else layer_count
    max_layers = min(max_layers, layer_count)
    session = locate_session(pid, profile, layer_count, args.max_seconds)
    table_address = int(session["table_address"])

    layers = []
    for index, pointer in iter_layer_pointers(pid, table_address, max_layers):
        raw = read_process_memory(pid, pointer, blob_size)
        if len(raw) != blob_size:
            print(f"Layer {index} short read ({len(raw)} bytes), skipping.", flush=True)
            layers.append({
                "index": index,
                "pointer": pointer,
                "summary": None,
                "blob_b64": None,
                "extra_fragments": {},
                "skipped": True,
            })
            continue
        extra_frags = {}
        if len(raw) >= 0x7C:
            extra_frags["0x38"] = base64.b64encode(raw[0x38:0x40]).decode("ascii")
            extra_frags["0x48"] = base64.b64encode(raw[0x48:0x60]).decode("ascii")
            extra_frags["0x68"] = base64.b64encode(raw[0x68:0x7C]).decode("ascii")
        layers.append({
            "index": index,
            "pointer": pointer,
            "summary": summarize_blob(raw, profile),
            "blob_b64": base64.b64encode(raw).decode("ascii"),
            "extra_fragments": extra_frags,
        })
        if index == 0 or (index + 1) % 100 == 0 or index + 1 == max_layers:
            print(f"Exported layer {index + 1}/{max_layers}", flush=True)

    payload = {
        "format": FORMAT_NAME,
        "created": time.time(),
        "game": profile.key,
        "process": psutil.Process(pid).name(),
        "pid": pid,
        "layer_count": layer_count,
        "exported_layers": len(layers),
        "blob_size": blob_size,
        "session": {
            "locator": session.get("locator"),
            "count_address": session.get("count_address"),
            "table_address": session.get("table_address"),
            "score": session.get("score"),
        },
        "offsets": {
            "position": profile.layer_position_offset,
            "scale": profile.layer_scale_offset,
            "rotation": profile.layer_rotation_offset,
            "color": profile.layer_color_offset,
            "mask": profile.layer_mask_offset,
            "shape_id_byte": profile.layer_shape_id_offset,
        },
        "layers": layers,
    }
    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output} ({len(layers)} layers, blob_size=0x{blob_size:x})")


def restore_raw(args):
    if not args.i_understand_this_can_crash_fh6:
        raise RuntimeError(
            "restore-raw is disabled by default because full raw blob writes crashed FH6. "
            "Use restore-known-fields instead, or pass --i-understand-this-can-crash-fh6 for manual experiments."
        )

    dump = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if dump.get("format") != FORMAT_NAME:
        raise RuntimeError(f"Unsupported dump format: {dump.get('format')!r}")

    modules = fh6_modules()
    get_profile = modules["get_profile"]
    dereference_pointer = modules["dereference_pointer"]
    write_process_memory = modules["write_process_memory"]

    profile = get_profile(args.game or dump.get("game", "fh6"))
    pid = args.pid or find_pid(profile)
    layer_count = int(args.layer_count or dump["layer_count"])
    dump_count = int(dump["layer_count"])
    if layer_count != dump_count and not args.allow_count_mismatch:
        raise RuntimeError(
            f"Current layer count {layer_count} differs from dump layer count {dump_count}. "
            "Use --allow-count-mismatch to restore the overlapping prefix only."
        )

    session = locate_session(pid, profile, layer_count, args.max_seconds)
    table_address = int(session["table_address"])
    layers = dump.get("layers", [])
    limit = min(len(layers), layer_count)
    if args.max_layers:
        limit = min(limit, int(args.max_layers))

    for item in layers[:limit]:
        index = int(item["index"])
        if index >= layer_count:
            continue
        raw = base64.b64decode(item["blob_b64"])
        pointer = dereference_pointer(pid, table_address + index * 8)
        write_process_memory(pid, pointer, raw)
        if index == 0 or (index + 1) % 100 == 0 or index + 1 == limit:
            print(f"Restored layer {index + 1}/{limit}", flush=True)
    print(f"Restored {limit} raw layer blobs.")


def restore_known_fields(args):
    dump = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if dump.get("format") != FORMAT_NAME:
        raise RuntimeError(f"Unsupported dump format: {dump.get('format')!r}")

    modules = fh6_modules()
    get_profile = modules["get_profile"]
    dereference_pointer = modules["dereference_pointer"]
    write_process_memory = modules["write_process_memory"]

    profile = get_profile(args.game or dump.get("game", "fh6"))
    pid = args.pid or find_pid(profile)
    layer_count = int(args.layer_count or dump["layer_count"])
    dump_count = int(dump["layer_count"])
    if layer_count != dump_count and not args.allow_count_mismatch:
        raise RuntimeError(
            f"Current layer count {layer_count} differs from dump layer count {dump_count}. "
            "Use --allow-count-mismatch to restore the overlapping prefix only."
        )

    session = locate_session(pid, profile, layer_count, args.max_seconds)
    table_address = int(session["table_address"])
    layers = dump.get("layers", [])
    limit = min(len(layers), layer_count)
    if args.max_layers:
        limit = min(limit, int(args.max_layers))

    SHAPE_SCALE_DIVISOR = {102: 63}

    for item in layers[:limit]:
        index = int(item["index"])
        if index >= layer_count:
            continue
        if item.get("skipped"):
            if index == 0 or (index + 1) % 100 == 0 or index + 1 == limit:
                print(f"Skipping layer {index + 1}/{limit} (unreadable in dump)", flush=True)
            continue
        pointer = dereference_pointer(pid, table_address + index * 8)
        if not pointer:
            print(f"Layer {index + 1}/{limit} pointer is null, skipping", flush=True)
            continue

        summary = item.get("summary")
        if not summary:
            continue
        pos = summary.get("position", [0.0, 0.0])
        scale = summary.get("scale", [0.0, 0.0])
        rot = summary.get("rotation", 0.0)
        color = summary.get("color", [0, 0, 0, 0])
        mask = summary.get("mask", 0)
        shape_id = summary.get("shape_id_byte", 0)

        if not pos or len(pos) < 2:
            pos = [0.0, 0.0]
        if not scale or len(scale) < 2:
            scale = [0.0, 0.0]
        if not color or len(color) < 4:
            color = [0, 0, 0, 0]

        # 1. Write extra fragments first (our approach: preserves transform matrix)
        frags = item.get("extra_fragments", {})
        for offset_str, blob_b64 in frags.items():
            frag_data = base64.b64decode(blob_b64)
            frag_offset = int(offset_str, 16)
            write_process_memory(pid, pointer + frag_offset, frag_data)

        # 2. Write known fields on top (our draw_memory_shape logic)
        pos_data = struct.pack('f', pos[0]) + struct.pack('f', pos[1])
        write_process_memory(pid, pointer + profile.layer_position_offset, pos_data)

        divisor = SHAPE_SCALE_DIVISOR.get(shape_id, 127)
        scale_data = struct.pack('f', scale[0]) + struct.pack('f', scale[1])
        write_process_memory(pid, pointer + profile.layer_scale_offset, scale_data)

        rot_data = struct.pack('f', rot)
        write_process_memory(pid, pointer + profile.layer_rotation_offset, rot_data)

        color_data = struct.pack('BBBB', color[0], color[1], color[2], color[3])
        write_process_memory(pid, pointer + profile.layer_color_offset, color_data)

        write_process_memory(pid, pointer + profile.layer_mask_offset, struct.pack('B', 1 if mask else 0))
        write_process_memory(pid, pointer + profile.layer_shape_id_offset, struct.pack('B', shape_id))

        if index == 0 or (index + 1) % 100 == 0 or index + 1 == limit:
            print(f"Restored layer {index + 1}/{limit} via structured write", flush=True)
    print(f"Restored {limit} layers using draw_memory_shape logic + extra_fragments.")


def restore_fields(args):
    dump = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if dump.get("format") != FORMAT_NAME:
        raise RuntimeError(f"Unsupported dump format: {dump.get('format')!r}")

    modules = fh6_modules()
    get_profile = modules["get_profile"]
    dereference_pointer = modules["dereference_pointer"]
    write_process_memory = modules["write_process_memory"]

    profile = get_profile(args.game or dump.get("game", "fh6"))
    pid = args.pid or find_pid(profile)
    layer_count = int(args.layer_count or dump["layer_count"])
    dump_count = int(dump["layer_count"])
    if layer_count != dump_count and not args.allow_count_mismatch:
        raise RuntimeError(
            f"Current layer count {layer_count} differs from dump layer count {dump_count}. "
            "Use --allow-count-mismatch to restore the overlapping prefix only."
        )

    requested = {field.strip() for field in args.fields.split(",") if field.strip()}
    spec_by_name = {
        name: (getattr(profile, offset_attr), size)
        for name, offset_attr, size in KNOWN_FIELD_SPECS
    }
    unknown = sorted(requested - set(spec_by_name))
    if unknown:
        raise RuntimeError(f"Unknown field(s): {', '.join(unknown)}. Known fields: {', '.join(spec_by_name)}")

    session = locate_session(pid, profile, layer_count, args.max_seconds)
    table_address = int(session["table_address"])
    layers = dump.get("layers", [])
    limit = min(len(layers), layer_count)
    if args.max_layers:
        limit = min(limit, int(args.max_layers))

    for item in layers[:limit]:
        index = int(item["index"])
        if index >= layer_count:
            continue
        raw = base64.b64decode(item["blob_b64"])
        pointer = dereference_pointer(pid, table_address + index * 8)
        for field in requested:
            offset, size = spec_by_name[field]
            write_process_memory(pid, pointer + offset, raw[offset:offset + size])
        if index == 0 or (index + 1) % 100 == 0 or index + 1 == limit:
            print(f"Restored {','.join(sorted(requested))} for layer {index + 1}/{limit}", flush=True)
    print(f"Restored {','.join(sorted(requested))} for {limit} layers.")


def copy_shape_from_layer(args):
    modules = fh6_modules()
    get_profile = modules["get_profile"]
    dereference_pointer = modules["dereference_pointer"]
    read_process_memory = modules["read_process_memory"]
    write_process_memory = modules["write_process_memory"]

    profile = get_profile(args.game)
    pid = args.pid or find_pid(profile)
    layer_count = int(args.layer_count)
    source_layer = int(args.source_layer)
    if source_layer < 0 or source_layer >= layer_count:
        raise RuntimeError(f"Source layer {source_layer} is outside 0..{layer_count - 1}.")

    target_start = int(args.target_start)
    target_end = int(args.target_end) if args.target_end is not None else layer_count - 1
    target_start = max(0, target_start)
    target_end = min(layer_count - 1, target_end)
    if target_start > target_end:
        raise RuntimeError("Target range is empty.")

    session = locate_session(pid, profile, layer_count, args.max_seconds)
    table_address = int(session["table_address"])
    source_label = "live"
    if args.source_dump:
        source_label = str(args.source_dump)
        dump = json.loads(Path(args.source_dump).read_text(encoding="utf-8"))
        if dump.get("format") != FORMAT_NAME:
            raise RuntimeError(f"Unsupported dump format: {dump.get('format')!r}")
        source_item = next(
            (item for item in dump.get("layers", []) if int(item["index"]) == source_layer),
            None,
        )
        if source_item is None:
            raise RuntimeError(f"Source dump does not contain layer {source_layer}.")
        source_blob = base64.b64decode(source_item["blob_b64"])
    else:
        source_pointer = dereference_pointer(pid, table_address + source_layer * 8)
        source_blob = read_process_memory(pid, source_pointer, DEFAULT_BLOB_SIZE)
    if len(source_blob) != DEFAULT_BLOB_SIZE:
        raise RuntimeError(f"Source layer short read: {len(source_blob)} / {DEFAULT_BLOB_SIZE} bytes.")

    shape_pointer = int.from_bytes(source_blob[0xA8:0xB0], byteorder=sys.byteorder)
    shape_probe = read_process_memory(pid, shape_pointer, 16)
    if len(shape_probe) < 16:
        raise RuntimeError(f"Source shape pointer 0x{shape_pointer:x} is not readable.")

    print(f"Source: {source_label}")
    print(f"Source layer: {source_layer}")
    print(f"Source shape_id_byte: {source_blob[0x7A]}")
    print(f"Source shape_vertex_count: {int.from_bytes(source_blob[0x58:0x5C], byteorder=sys.byteorder)}")
    print(f"Source shape_resource_pointer: 0x{shape_pointer:x}")
    print(f"Target range: {target_start}..{target_end} excluding source")
    if args.dry_run:
        print("Dry run only; no memory was written.")
        return

    written = 0
    for index in range(target_start, target_end + 1):
        if index == source_layer:
            continue
        pointer = dereference_pointer(pid, table_address + index * 8)
        for _name, offset, size in SHAPE_FIELD_SPECS:
            write_process_memory(pid, pointer + offset, source_blob[offset:offset + size])
        written += 1
        if written == 1 or written % 100 == 0 or index == target_end:
            print(f"Copied shape fields to layer {index + 1}/{layer_count}", flush=True)
    print(f"Copied shape fields from layer {source_layer} to {written} layer(s).")


def load_dump_blobs(path):
    dump = json.loads(Path(path).read_text(encoding="utf-8"))
    if dump.get("format") != FORMAT_NAME:
        raise RuntimeError(f"Unsupported dump format: {dump.get('format')!r}")
    blobs = {
        int(item["index"]): base64.b64decode(item["blob_b64"])
        for item in dump.get("layers", [])
    }
    return dump, blobs


def compare_dumps(args):
    dump_a, blobs_a = load_dump_blobs(args.a)
    dump_b, blobs_b = load_dump_blobs(args.b)
    common = sorted(set(blobs_a) & set(blobs_b))
    if args.layer is not None:
        common = [int(args.layer)] if int(args.layer) in blobs_a and int(args.layer) in blobs_b else []
    if args.max_layers:
        common = common[:int(args.max_layers)]
    if not common:
        raise RuntimeError("No common layers to compare.")

    counts = Counter()
    examples = defaultdict(list)
    for index in common:
        blob_a = blobs_a[index]
        blob_b = blobs_b[index]
        for offset, (byte_a, byte_b) in enumerate(zip(blob_a, blob_b)):
            if byte_a == byte_b:
                continue
            counts[offset] += 1
            if len(examples[offset]) < int(args.examples):
                examples[offset].append((index, byte_a, byte_b))

    print(f"A: {args.a} layers={dump_a.get('exported_layers')} blob_size={dump_a.get('blob_size')}")
    print(f"B: {args.b} layers={dump_b.get('exported_layers')} blob_size={dump_b.get('blob_size')}")
    print(f"Compared layers: {len(common)}")
    print(f"Different offsets: {len(counts)}")
    print("Known field ranges: position 0x18-0x1f, scale 0x28-0x2f, rotation 0x50-0x53, color 0x74-0x77, mask 0x78, shape_id_byte 0x7a")
    for offset, count in counts.most_common(int(args.top)):
        sample = " ".join(
            f"L{index}:{byte_a:02x}->{byte_b:02x}"
            for index, byte_a, byte_b in examples[offset]
        )
        print(f"+0x{offset:03x} {count:4d}/{len(common)} {sample}")


def build_parser():
    parser = argparse.ArgumentParser(description="Experimental FH6 raw layer dump/restore tool.")
    sub = parser.add_subparsers(dest="command", required=True)

    export_parser = sub.add_parser("export", help="Export current FH6 layer blobs.")
    export_parser.add_argument("--game", default="fh6")
    export_parser.add_argument("--pid", type=int, default=None)
    export_parser.add_argument("--layer-count", type=int, required=True)
    export_parser.add_argument("--blob-size", default=hex(DEFAULT_BLOB_SIZE))
    export_parser.add_argument("--max-layers", type=int, default=None)
    export_parser.add_argument("--max-seconds", type=int, default=45)
    export_parser.add_argument("--output", required=True)
    export_parser.set_defaults(func=export_dump)

    restore_parser = sub.add_parser("restore-raw", help="Restore raw FH6 layer blobs.")
    restore_parser.add_argument("--game", default=None)
    restore_parser.add_argument("--pid", type=int, default=None)
    restore_parser.add_argument("--layer-count", type=int, default=None)
    restore_parser.add_argument("--max-layers", type=int, default=None)
    restore_parser.add_argument("--max-seconds", type=int, default=45)
    restore_parser.add_argument("--input", required=True)
    restore_parser.add_argument("--allow-count-mismatch", action="store_true")
    restore_parser.add_argument("--i-understand-this-can-crash-fh6", action="store_true")
    restore_parser.set_defaults(func=restore_raw)

    safe_restore_parser = sub.add_parser("restore-known-fields", help="Restore only known stable FH6 layer fields.")
    safe_restore_parser.add_argument("--game", default=None)
    safe_restore_parser.add_argument("--pid", type=int, default=None)
    safe_restore_parser.add_argument("--layer-count", type=int, default=None)
    safe_restore_parser.add_argument("--max-layers", type=int, default=None)
    safe_restore_parser.add_argument("--max-seconds", type=int, default=45)
    safe_restore_parser.add_argument("--input", required=True)
    safe_restore_parser.add_argument("--allow-count-mismatch", action="store_true")
    safe_restore_parser.set_defaults(func=restore_known_fields)

    fields_restore_parser = sub.add_parser("restore-fields", help="Restore selected known FH6 layer fields.")
    fields_restore_parser.add_argument("--game", default=None)
    fields_restore_parser.add_argument("--pid", type=int, default=None)
    fields_restore_parser.add_argument("--layer-count", type=int, default=None)
    fields_restore_parser.add_argument("--max-layers", type=int, default=None)
    fields_restore_parser.add_argument("--max-seconds", type=int, default=45)
    fields_restore_parser.add_argument("--input", required=True)
    fields_restore_parser.add_argument("--fields", required=True, help="Comma-separated fields, e.g. mask or color,mask")
    fields_restore_parser.add_argument("--allow-count-mismatch", action="store_true")
    fields_restore_parser.set_defaults(func=restore_fields)

    copy_shape_parser = sub.add_parser("copy-shape-from-layer", help="Copy current-session shape fields from one FH6 layer to others.")
    copy_shape_parser.add_argument("--game", default="fh6")
    copy_shape_parser.add_argument("--pid", type=int, default=None)
    copy_shape_parser.add_argument("--layer-count", type=int, required=True)
    copy_shape_parser.add_argument("--source-layer", type=int, default=0)
    copy_shape_parser.add_argument("--source-dump", default=None)
    copy_shape_parser.add_argument("--target-start", type=int, default=0)
    copy_shape_parser.add_argument("--target-end", type=int, default=None)
    copy_shape_parser.add_argument("--max-seconds", type=int, default=45)
    copy_shape_parser.add_argument("--dry-run", action="store_true")
    copy_shape_parser.set_defaults(func=copy_shape_from_layer)

    compare_parser = sub.add_parser("compare-dumps", help="Compare two raw FH6 layer dumps by byte offset.")
    compare_parser.add_argument("--a", required=True)
    compare_parser.add_argument("--b", required=True)
    compare_parser.add_argument("--layer", type=int, default=None)
    compare_parser.add_argument("--max-layers", type=int, default=None)
    compare_parser.add_argument("--top", type=int, default=80)
    compare_parser.add_argument("--examples", type=int, default=5)
    compare_parser.set_defaults(func=compare_dumps)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
