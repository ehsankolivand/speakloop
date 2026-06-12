"""Public types for read-aloud pronunciation scoring (016).

Contains NO engine import (torch/transformers stay function-local in
``wav2vec2_engine.py`` only — Principle V). These dataclasses + the
``PronunciationScorer`` Protocol are the stable contract every consumer codes
against, so swapping the acoustic model touches one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol


@dataclass(frozen=True)
class PhoneFlag:
    """One sound that scored as off in a read-aloud drill.

    ``expected`` is the canonical phone (the DETECTION — reliable). ``competitor``
    is the top competing phone over the same frames (a DIAGNOSIS *suggestion* —
    unreliable; only surfaced when ``confident_diagnosis`` is True). FR-009.
    """

    expected: str
    word: str
    gop: float
    competitor: str | None = None
    competitor_margin: float = 0.0
    confident_diagnosis: bool = False
    tip: str = ""


@dataclass(frozen=True)
class DrillResult:
    """The outcome of scoring one read-aloud drill."""

    drill_id: str
    text: str
    contrast_id: str
    status: Literal["scored", "not_captured", "error"]
    flags: list[PhoneFlag] = field(default_factory=list)
    detail: str = ""

    @property
    def has_flags(self) -> bool:
        return bool(self.flags)


class PronunciationError(Exception):
    """Single public error base for the pronunciation module."""


class PronunciationScorer(Protocol):
    """Scores a recorded read-aloud against a known canonical phoneme sequence.

    Implementations MUST NOT raise into the session: a silent/empty recording →
    ``DrillResult(status="not_captured")``; a model/scoring failure →
    ``DrillResult(status="error", detail=...)``. Pure w.r.t. global state.
    """

    def score(
        self,
        wav_path: Path,
        *,
        canonical: list[str],
        targets: list[dict],
        tip: str,
        competitors: list[str],
        drill_id: str,
        text: str,
        contrast_id: str,
    ) -> DrillResult: ...
