"""Post-download size validation (FR-022). Corrupt is treated identically to missing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from speakloop.installer.manifest import Model

Reason = Literal["ok", "missing", "size_mismatch"]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: Reason
    measured_bytes: int = 0
    expected_bytes: int = 0


# Allow generous tolerance because expected_size_bytes is approximate.
SIZE_TOLERANCE = 0.25


def _directory_size(path) -> int:
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def validate(model: Model) -> ValidationResult:
    """Validate that `model.local_path` exists and is roughly the right size."""
    path = model.local_path
    if not path.exists() or not path.is_dir():
        return ValidationResult(
            ok=False, reason="missing", expected_bytes=model.expected_size_bytes
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
