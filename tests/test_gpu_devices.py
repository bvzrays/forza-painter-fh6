from __future__ import annotations

import gpu_devices
from generator_backend import build_generator_env
from gpu_devices import (
    GpuDevice,
    _vendor_kind,
    device_env_overrides,
    find_device,
    find_device_by_label,
)


def make_device(
    key="amd|Test|8192|32|0",
    name="gfx1201",
    board_name="AMD Radeon RX 9070 XT",
    vendor="Advanced Micro Devices, Inc.",
    vendor_kind="amd",
    device_index=0,
    memory_mb=16304,
    compute_units=32,
    occurrence=0,
):
    return GpuDevice(
        key=key,
        name=name,
        board_name=board_name,
        vendor=vendor,
        vendor_kind=vendor_kind,
        platform_name="Test Platform",
        platform_index=0,
        device_index=device_index,
        memory_mb=memory_mb,
        compute_units=compute_units,
        is_discrete=True,
        occurrence=occurrence,
    )


class TestVendorKind:
    def test_nvidia(self):
        assert _vendor_kind("NVIDIA Corporation", "NVIDIA GeForce RTX 4080") == "nvidia"

    def test_amd(self):
        assert _vendor_kind("Advanced Micro Devices, Inc.", "gfx1201") == "amd"

    def test_intel(self):
        assert _vendor_kind("Intel(R) Corporation", "Intel(R) Arc(TM) A770") == "intel"

    def test_unknown(self):
        assert _vendor_kind("Some Vendor", "Some Device") == "other"


class TestGpuDeviceLabels:
    def test_label_has_memory_and_compute_units(self):
        assert make_device().label == "AMD Radeon RX 9070 XT (16 GB, 32 CU)"

    def test_label_without_details(self):
        device = make_device(memory_mb=0, compute_units=0)
        assert device.label == "AMD Radeon RX 9070 XT"

    def test_display_name_falls_back_to_device_name(self):
        assert make_device(board_name="").display_name == "gfx1201"

    def test_identical_cards_get_distinct_labels(self):
        first = make_device(occurrence=0)
        second = make_device(occurrence=1)
        assert first.label != second.label
        assert second.label.endswith("#2")

    def test_can_be_forced(self):
        assert make_device(vendor_kind="amd").can_be_forced
        assert make_device(vendor_kind="nvidia").can_be_forced
        assert not make_device(vendor_kind="intel").can_be_forced


class TestDeviceLookup:
    def test_find_device_by_key(self):
        devices = [make_device(key="a"), make_device(key="b")]
        assert find_device("b", devices) is devices[1]

    def test_find_device_missing_key(self):
        assert find_device("gone", [make_device(key="a")]) is None

    def test_find_device_empty_key_never_matches(self):
        assert find_device("", [make_device(key="a")]) is None

    def test_find_device_by_label(self):
        devices = [make_device(board_name="Card A"), make_device(board_name="Card B")]
        assert find_device_by_label("Card B (16 GB, 32 CU)", devices) is devices[1]

    def test_find_device_by_label_missing(self):
        assert find_device_by_label("Automatic", [make_device()]) is None


class TestDeviceEnvOverrides:
    def test_automatic_selection_has_no_overrides(self):
        assert device_env_overrides(None, [make_device()]) == {}

    def test_amd_uses_device_ordinal(self):
        device = make_device(vendor_kind="amd", device_index=1)
        assert device_env_overrides(device, [device]) == {"GPU_DEVICE_ORDINAL": "1"}

    def test_nvidia_uses_visible_devices(self):
        device = make_device(vendor_kind="nvidia", device_index=2)
        assert device_env_overrides(device, [device]) == {"CUDA_VISIBLE_DEVICES": "2"}

    def test_intel_cannot_be_forced(self):
        device = make_device(vendor_kind="intel")
        assert device_env_overrides(device, [device]) == {}

    def test_other_vendors_are_hidden(self):
        amd = make_device(key="amd", vendor_kind="amd", device_index=1)
        nvidia = make_device(key="nv", vendor_kind="nvidia", device_index=0)
        assert device_env_overrides(amd, [amd, nvidia]) == {
            "GPU_DEVICE_ORDINAL": "1",
            "CUDA_VISIBLE_DEVICES": "-1",
        }

    def test_same_vendor_siblings_are_not_hidden(self):
        first = make_device(key="a", vendor_kind="amd", device_index=0)
        second = make_device(key="b", vendor_kind="amd", device_index=1)
        assert device_env_overrides(second, [first, second]) == {"GPU_DEVICE_ORDINAL": "1"}


class TestGeneratorEnv:
    def test_overrides_survive_the_sanitizer(self):
        # CUDA_VISIBLE_DEVICES is on the drop list, so a deliberate override has
        # to be applied after sanitizing or GPU pinning silently does nothing.
        env = build_generator_env({"CUDA_VISIBLE_DEVICES": "1", "GPU_DEVICE_ORDINAL": "0"})
        assert env["CUDA_VISIBLE_DEVICES"] == "1"
        assert env["GPU_DEVICE_ORDINAL"] == "0"

    def test_inherited_gpu_variables_are_still_dropped(self, monkeypatch):
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "7")
        assert "CUDA_VISIBLE_DEVICES" not in build_generator_env()

    def test_env_stays_sanitized(self):
        env = build_generator_env({"GPU_DEVICE_ORDINAL": "1"})
        assert env["FORZA_PAINTER_GENERATOR_SANITIZED_ENV"] == "1"

    def test_values_are_stringified(self):
        assert build_generator_env({"GPU_DEVICE_ORDINAL": 3})["GPU_DEVICE_ORDINAL"] == "3"


class TestEnumerationFallback:
    def test_no_icd_loader_returns_no_devices(self, monkeypatch):
        monkeypatch.setattr(gpu_devices, "_load_opencl", lambda: None)
        assert gpu_devices.list_gpu_devices(refresh=True) == []

    def test_enumeration_failure_is_not_fatal(self, monkeypatch):
        def boom():
            raise OSError("driver exploded")

        monkeypatch.setattr(gpu_devices, "_enumerate_devices", boom)
        assert gpu_devices.list_gpu_devices(refresh=True) == []
