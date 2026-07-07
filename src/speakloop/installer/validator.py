"""Post-download size validation (FR-022). Corrupt is treated identically to missing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from speakloop.installer.manifest import Model

Reason = Literal["ok", "missing", "size_mismatch", "incomplete"]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: Reason
    measured_bytes: int = 0
    expected_bytes: int = 0


# Allow generous tolerance because expected_size_bytes is approximate.
SIZE_TOLERANCE = 0.25

# Control/marker files a killed download leaves behind: aria2c writes a
# `<shard>.aria2` control file next to each shard until that shard finishes, and
# `huggingface_hub.snapshot_download` leaves `*.incomplete` markers. Their presence
# means the download was interrupted (Ctrl-C / crash / power loss) even when the
# partial bytes already clear the size tolerance (007's headline resumable guarantee).
_INCOMPLETE_GLOBS = ("*.aria2", "*.incomplete")


def _directory_size(path) -> int:
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def _has_incomplete_download(path) -> bool:
    """True if any interrupted-download control/marker file remains under `path`."""
    return any(next(path.rglob(glob), None) is not None for glob in _INCOMPLETE_GLOBS)


def validate(model: Model) -> ValidationResult:
    """Validate that `model.local_path` exists and is roughly the right size."""
    path = model.local_path
    if not path.exists() or not path.is_dir():
        return ValidationResult(
            ok=False, reason="missing", expected_bytes=model.expected_size_bytes
        )

    # A download interrupted past the size tolerance would otherwise pass the byte
    # check below and be treated as complete — never resumed. Catch it first so
    # `_missing_or_invalid` re-queues the model and aria2 (`--continue=true`) /
    # snapshot (`resume_download=True`) finish it (FR-022 / 007 resume guarantee).
    if _has_incomplete_download(path):
        return ValidationResult(
            ok=False,
            reason="incomplete",
            measured_bytes=_directory_size(path),
            expected_bytes=model.expected_size_bytes,
        )

    measured = _directory_size(path)
    if measured == 0:
        return ValidationResult(
            ok=False, reason="missing", expected_bytes=model.expected_size_bytes
        )

    lo = model.expected_size_bytes * (1 - SIZE_TOLERANCE)
    if measured < lo:
        return ValidationResult(
            ok=False,
            reason="size_mismatch",
            measured_bytes=measured,
            expected_bytes=model.expected_size_bytes,
        )
    return ValidationResult(
        ok=True,
        reason="ok",
        measured_bytes=measured,
        expected_bytes=model.expected_size_bytes,
    )
