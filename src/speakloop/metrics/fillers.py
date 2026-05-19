"""Filler-word metric (FR-012a). Canonical 10-token set."""

from __future__ import annotations

import re

# Canonical 10-token set per FR-012a. Order is irrelevant; case-insensitive match.
FILLER_TOKENS: tuple[str, ...] = (
    "um",
    "uh",
    "ah",
    "er",
    "hmm",
    "like",
    "you know",
    "i mean",
    "basically",
    "actually",
)


def _build_pattern() -> re.Pattern[str]:
    """Whole-word/-phrase pattern, longest first to prevent overlap."""
    sorted_tokens = sorted(FILLER_TOKENS, key=len, reverse=True)
    parts = [re.escape(t).replace(r"\ ", r"\s+") for t in sorted_tokens]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_FILLER_RE = _build_pattern()

# Word tokenizer matching speech_rate.words_total (excludes punctuation-only).
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def filler_words_count(text: str) -> int:
    return len(_FILLER_RE.findall(text or ""))


def filler_density_per_100_words(text: str) -> float:
    n_total = len(_WORD_RE.findall(text or ""))
    if n_total == 0:
        return 0.0
    return filler_words_count(text) / n_total * 100.0


def compute(text: str) -> dict[str, float | int]:
    return {
        "filler_words_count": filler_words_count(text),
        "filler_density_per_100_words": round(filler_density_per_100_words(text), 1),
    }
