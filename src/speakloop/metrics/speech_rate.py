"""Speech-rate metric (data-model.md §5)."""

from __future__ import annotations

import re

from speakloop.asr import Transcript

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def words_total(text: str) -> int:
    """Count word tokens, excluding pure punctuation."""
    return len(_WORD_RE.findall(text or ""))


def speech_rate_wpm(transcript: Transcript) -> float:
    """`words_total / (actual_duration_seconds / 60)`. Returns 0.0 on zero duration."""
    n = words_total(transcript.text)
    duration = transcript.audio_duration_seconds
    if duration <= 0:
        return 0.0
    return n / (duration / 60.0)


def compute(transcript: Transcript) -> dict[str, float | int]:
    return {
        "words_total": words_total(transcript.text),
        "speech_rate_wpm": round(speech_rate_wpm(transcript), 1),
    }
