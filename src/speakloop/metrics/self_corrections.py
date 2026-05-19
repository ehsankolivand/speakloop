"""Self-corrections metric (FR-012c). Deterministic transcript-only heuristic.

MUST NOT import speakloop.llm — this is a transcript-only signal.
"""

from __future__ import annotations

import re

REPAIR_MARKERS: tuple[str, ...] = (
    "i mean",
    "sorry",
    "let me rephrase",
    "actually no",
    "what i meant",
    "wait",
)


def _build_repair_pattern() -> re.Pattern[str]:
    parts = [re.escape(m).replace(r"\ ", r"\s+") for m in REPAIR_MARKERS]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_REPAIR_RE = _build_repair_pattern()
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def verbatim_repeat_count(text: str) -> int:
    """Count consecutive duplicate-word pairs (e.g. 'the the', 'I I')."""
    tokens = [t.lower() for t in _WORD_RE.findall(text or "")]
    count = 0
    i = 1
    while i < len(tokens):
        if tokens[i] == tokens[i - 1]:
            count += 1
            i += 2  # don't double-count overlapping triples
        else:
            i += 1
    return count


def repair_marker_count(text: str) -> int:
    return len(_REPAIR_RE.findall(text or ""))


def self_corrections_count(text: str) -> int:
    return verbatim_repeat_count(text) + repair_marker_count(text)


def compute(text: str) -> dict[str, int]:
    return {"self_corrections_count": self_corrections_count(text)}
