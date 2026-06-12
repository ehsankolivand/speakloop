"""Read-aloud pronunciation drills (016): scoring + safety gate + drill bank + wording.

Single-responsibility module (Principle IV). The heavy acoustic model (torch +
transformers) is confined to ``wav2vec2_engine.py`` and imported function-local, so
``import speakloop.pronunciation`` (and ``speakloop --help``) load NO engine package.
"""

from __future__ import annotations

from speakloop.pronunciation.drill_bank import (
    Contrast,
    Drill,
    DrillBank,
    DrillBankError,
    load_drill_bank,
)
from speakloop.pronunciation.drill_runner import (
    DrillQuit,
    build_block_result,
    contrast_label,
    flagged_contrast_counts,
    run_drill_item,
    select_drills,
)
from speakloop.pronunciation.feedback import live_flag_summary, render_drills_section
from speakloop.pronunciation.gate import (
    SafetyDecision,
    assess_safety,
    assess_standalone_safety,
)
from speakloop.pronunciation.interface import (
    DrillResult,
    PhoneFlag,
    PronunciationError,
    PronunciationScorer,
)


def build_scorer() -> PronunciationScorer:
    """Construct the wav2vec2-backed scorer (lazy import keeps the heavy deps off the
    ``import speakloop.pronunciation`` path)."""
    from speakloop.pronunciation.wav2vec2_engine import build_scorer as _build

    return _build()


__all__ = [
    "Contrast",
    "Drill",
    "DrillBank",
    "DrillBankError",
    "DrillQuit",
    "DrillResult",
    "PhoneFlag",
    "PronunciationError",
    "PronunciationScorer",
    "SafetyDecision",
    "assess_safety",
    "assess_standalone_safety",
    "build_block_result",
    "build_scorer",
    "contrast_label",
    "flagged_contrast_counts",
    "live_flag_summary",
    "load_drill_bank",
    "render_drills_section",
    "run_drill_item",
    "select_drills",
]
