"""Detect OpenCL GPUs and pin the bundled generator to a chosen one.

The bundled generator (``forza-painter-geometrize-go.exe``) has no device flag:
it enumerates OpenCL devices itself and keeps the "best" one it finds (GPU
first, then discrete, then most VRAM, then most compute units). Vendor OpenCL
runtimes do honour ordinal environment variables, so this module enumerates the
same devices through the ICD loader and builds an environment where only the
requested GPU stays visible to the generator.

Enumeration only reads device properties; no OpenCL context is created, so it
stays cheap and cannot disturb a running generation.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import POINTER, byref, c_size_t, c_uint, c_ulonglong, c_void_p, create_string_buffer
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# OpenCL constants
# ---------------------------------------------------------------------------

CL_SUCCESS = 0
CL_DEVICE_TYPE_GPU = 1 << 2
CL_DEVICE_TYPE_ALL = 0xFFFFFFFF

CL_PLATFORM_NAME = 0x0902
CL_PLATFORM_VENDOR = 0x0903

CL_DEVICE_TYPE = 0x1000
CL_DEVICE_MAX_COMPUTE_UNITS = 0x1002
CL_DEVICE_GLOBAL_MEM_SIZE = 0x101F
CL_DEVICE_NAME = 0x102B
CL_DEVICE_VENDOR = 0x102C
CL_DEVICE_HOST_UNIFIED_MEMORY = 0x1035
# AMD extension; the only reliable source of a marketing name such as
# "AMD Radeon RX 9070 XT" instead of the kernel name "gfx1201".
CL_DEVICE_BOARD_NAME_AMD = 0x4038

_OPENCL_LIBRARY_NAMES = ("OpenCL.dll", "libOpenCL.so.1", "libOpenCL.so")

# Environment variables that force a vendor runtime down to a single device.
# GPU_DEVICE_ORDINAL is verified against the bundled generator on AMD;
# CUDA_VISIBLE_DEVICES is the documented NVIDIA equivalent and also filters
# their OpenCL device list.
_ORDINAL_ENV_VARS = {
    "amd": "GPU_DEVICE_ORDINAL",
    "nvidia": "CUDA_VISIBLE_DEVICES",
}

# Values that make a vendor runtime expose no device at all, so the generator
# cannot fall back to another vendor's card.
_HIDE_ENV_VALUES = {
    "amd": "9999",
    "nvidia": "-1",
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GpuDevice:
    """A single OpenCL GPU the bundled generator could run on."""

    key: str
    name: str
    board_name: str
    vendor: str
    vendor_kind: str
    platform_name: str
    platform_index: int
    device_index: int
    memory_mb: int
    compute_units: int
    is_discrete: bool
    occurrence: int = 0

    @property
    def display_name(self) -> str:
        return self.board_name or self.name or "Unknown device"

    @property
    def label(self) -> str:
        details = []
        if self.memory_mb:
            details.append(f"{self.memory_mb / 1024:.0f} GB")
        if self.compute_units:
            details.append(f"{self.compute_units} CU")
        label = self.display_name
        if details:
            label += f" ({', '.join(details)})"
        # Two identical cards would otherwise share one entry in the picker.
        if self.occurrence:
            label += f" #{self.occurrence + 1}"
        return label

    @property
    def can_be_forced(self) -> bool:
        return self.vendor_kind in _ORDINAL_ENV_VARS


# ---------------------------------------------------------------------------
# ICD loader access
# ---------------------------------------------------------------------------

def _load_opencl():
    for library_name in _OPENCL_LIBRARY_NAMES:
        try:
            lib = ctypes.CDLL(library_name)
        except OSError:
            continue
        try:
            lib.clGetPlatformIDs.argtypes = [c_uint, POINTER(c_void_p), POINTER(c_uint)]
            lib.clGetPlatformInfo.argtypes = [c_void_p, c_uint, c_size_t, c_void_p, POINTER(c_size_t)]
            lib.clGetDeviceIDs.argtypes = [c_void_p, c_ulonglong, c_uint, POINTER(c_void_p), POINTER(c_uint)]
            lib.clGetDeviceInfo.argtypes = [c_void_p, c_uint, c_size_t, c_void_p, POINTER(c_size_t)]
        except AttributeError:
            continue
        return lib
    return None


def _info_text(query, handle, param) -> str:
    size = c_size_t()
    if query(handle, c_uint(param), c_size_t(0), None, byref(size)) != CL_SUCCESS or not size.value:
        return ""
    buffer = create_string_buffer(size.value)
    if query(handle, c_uint(param), c_size_t(size.value), buffer, None) != CL_SUCCESS:
        return ""
    return buffer.value.decode("utf-8", "replace").strip()


def _device_number(lib, device, param, ctype):
    value = ctype()
    if lib.clGetDeviceInfo(device, c_uint(param), c_size_t(ctypes.sizeof(value)), byref(value), None) != CL_SUCCESS:
        return 0
    return value.value


def _vendor_kind(vendor: str, name: str) -> str:
    text = f"{vendor} {name}".lower()
    if "nvidia" in text:
        return "nvidia"
    if "advanced micro devices" in text or "amd" in text or "ati technologies" in text:
        return "amd"
    if "intel" in text:
        return "intel"
    return "other"


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

def _enumerate_devices() -> list[GpuDevice]:
    lib = _load_opencl()
    if lib is None:
        return []

    platform_count = c_uint()
    if lib.clGetPlatformIDs(0, None, byref(platform_count)) != CL_SUCCESS or not platform_count.value:
        return []
    platforms = (c_void_p * platform_count.value)()
    if lib.clGetPlatformIDs(platform_count.value, platforms, None) != CL_SUCCESS:
        return []

    devices: list[GpuDevice] = []
    # The same physical card shows up once per registered ICD, so an identical
    # entry coming from another platform index is collapsed into the first one.
    seen: set[tuple] = set()
    name_counts: dict[tuple, int] = {}

    for platform_index in range(platform_count.value):
        platform = c_void_p(platforms[platform_index])
        platform_name = _info_text(lib.clGetPlatformInfo, platform, CL_PLATFORM_NAME)
        platform_vendor = _info_text(lib.clGetPlatformInfo, platform, CL_PLATFORM_VENDOR)

        device_count = c_uint()
        if lib.clGetDeviceIDs(platform, CL_DEVICE_TYPE_ALL, 0, None, byref(device_count)) != CL_SUCCESS:
            continue
        if not device_count.value:
            continue
        handles = (c_void_p * device_count.value)()
        if lib.clGetDeviceIDs(platform, CL_DEVICE_TYPE_ALL, device_count.value, handles, None) != CL_SUCCESS:
            continue

        for device_index in range(device_count.value):
            device = c_void_p(handles[device_index])
            device_type = _device_number(lib, device, CL_DEVICE_TYPE, c_ulonglong)
            if not device_type & CL_DEVICE_TYPE_GPU:
                continue
            name = _info_text(lib.clGetDeviceInfo, device, CL_DEVICE_NAME)
            vendor = _info_text(lib.clGetDeviceInfo, device, CL_DEVICE_VENDOR) or platform_vendor
            board_name = _info_text(lib.clGetDeviceInfo, device, CL_DEVICE_BOARD_NAME_AMD)
            memory_mb = int(_device_number(lib, device, CL_DEVICE_GLOBAL_MEM_SIZE, c_ulonglong) // (1024 * 1024))
            compute_units = int(_device_number(lib, device, CL_DEVICE_MAX_COMPUTE_UNITS, c_uint))
            unified_memory = bool(_device_number(lib, device, CL_DEVICE_HOST_UNIFIED_MEMORY, c_uint))

            fingerprint = (device_index, name, board_name, vendor, memory_mb, compute_units)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            display = board_name or name or "gpu"
            # Counted per rendered label, so only truly identical cards are numbered.
            label_base = (display, memory_mb, compute_units)
            occurrence = name_counts.get(label_base, 0)
            name_counts[label_base] = occurrence + 1
            vendor_kind = _vendor_kind(vendor, name)

            devices.append(
                GpuDevice(
                    key=f"{vendor_kind}|{display}|{memory_mb}|{compute_units}|{occurrence}",
                    name=name,
                    board_name=board_name,
                    vendor=vendor,
                    vendor_kind=vendor_kind,
                    platform_name=platform_name,
                    platform_index=platform_index,
                    device_index=device_index,
                    memory_mb=memory_mb,
                    compute_units=compute_units,
                    is_discrete=not unified_memory,
                    occurrence=occurrence,
                )
            )
    return devices


_cache_lock = threading.Lock()
_cached_devices: list[GpuDevice] | None = None


def list_gpu_devices(refresh: bool = False) -> list[GpuDevice]:
    """Return the OpenCL GPUs on this machine; the enumeration is cached."""
    global _cached_devices
    with _cache_lock:
        if _cached_devices is not None and not refresh:
            return list(_cached_devices)
    try:
        devices = _enumerate_devices()
    except Exception:
        devices = []
    with _cache_lock:
        _cached_devices = devices
        return list(_cached_devices)


def find_device(key: str, devices: list[GpuDevice] | None = None) -> GpuDevice | None:
    """Return the device stored under *key*, or ``None`` when it is gone."""
    if not key:
        return None
    for device in devices if devices is not None else list_gpu_devices():
        if device.key == key:
            return device
    return None


def find_device_by_label(label: str, devices: list[GpuDevice] | None = None) -> GpuDevice | None:
    """Return the device shown as *label* in the UI, or ``None``."""
    if not label:
        return None
    for device in devices if devices is not None else list_gpu_devices():
        if device.label == label:
            return device
    return None


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

def device_env_overrides(
    device: GpuDevice | None, devices: list[GpuDevice] | None = None
) -> dict[str, str]:
    """Build the environment entries that pin the generator to *device*.

    Returns an empty mapping for automatic selection, and for vendors without a
    device-ordinal variable (Intel), where the generator keeps choosing on its
    own.
    """
    if device is None:
        return {}
    variable = _ORDINAL_ENV_VARS.get(device.vendor_kind)
    if not variable:
        return {}
    overrides = {variable: str(device.device_index)}
    for other in devices if devices is not None else list_gpu_devices():
        if other.vendor_kind == device.vendor_kind:
            continue
        hide_variable = _ORDINAL_ENV_VARS.get(other.vendor_kind)
        if hide_variable and hide_variable not in overrides:
            overrides[hide_variable] = _HIDE_ENV_VALUES[other.vendor_kind]
    return overrides
