"""Audio device enumeration (used by doctor + FR-009 pre-check)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float


def _query() -> tuple[list[dict[str, Any]], tuple[int | None, int | None]]:
    import sounddevice as sd

    devices = sd.query_devices()
    # `sd.default.device` is a `_InputOutputPair` on recent sounddevice versions
    # (not a list/tuple, so isinstance(..., (list, tuple)) is False). Both forms
    # support indexing, so unpack directly and let the try/except cover the
    # rare cases where it's something else.
    default = sd.default.device
    try:
        in_idx: int | None = int(default[0])
        out_idx: int | None = int(default[1])
    except (TypeError, IndexError, ValueError):
        in_idx, out_idx = None, None
    return list(devices), (in_idx, out_idx)


def _to_info(idx: int, d: dict[str, Any]) -> DeviceInfo:
    return DeviceInfo(
        index=idx,
        name=str(d.get("name", "<unknown>")),
        max_input_channels=int(d.get("max_input_channels", 0)),
        max_output_channels=int(d.get("max_output_channels", 0)),
        default_samplerate=float(d.get("default_samplerate", 0.0)),
    )


def default_input() -> DeviceInfo | None:
    try:
        devices, (in_idx, _out_idx) = _query()
    except Exception:
        return None
    if in_idx is None or in_idx < 0 or in_idx >= len(devices):
        return None
    info = _to_info(in_idx, devices[in_idx])
    if info.max_input_channels <= 0:
        return None
    return info


def default_output() -> DeviceInfo | None:
    try:
        devices, (_in_idx, out_idx) = _query()
    except Exception:
        return None
    if out_idx is None or out_idx < 0 or out_idx >= len(devices):
        return None
    info = _to_info(out_idx, devices[out_idx])
    if info.max_output_channels <= 0:
        return None
    return info


def list_devices() -> list[DeviceInfo]:
    try:
        devices, _ = _query()
    except Exception:
        return []
    return [_to_info(i, d) for i, d in enumerate(devices)]
