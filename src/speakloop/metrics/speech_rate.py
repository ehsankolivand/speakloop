"""Speech-rate metric (data-model.md §5)."""

from __future__ import annotations

import re

from speakloop.asr import Transcript

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def words_total(text: str) -> int:
    """Count word tokens, excluding pure punctuation."""
    return len(_WORD_RE.findall(text or ""))


def speech_rate_wpm(transcript: Transcript, *, real_speech_seconds: float | None = None) -> float:
    """`words_total / (duration / 60)`. Returns 0.0 on zero duration.

    ``real_speech_seconds`` (010, P4): when supplied (the summed length of the
    real-speech regions, after triage dropped silence/hallucination spans), it is
    the denominator instead of the full clip duration, so hallucinated silence does
    not deflate the rate. ``None`` ⇒ original behaviour (full clip duration).
    """
    n = words_total(transcript.text)
    duration = transcript.audio_duration_seconds if real_speech_seconds is None else real_speech_seconds
    if duration <= 0:
        return 0.0
    return n / (duration / 60.0)


def compute(
    transcript: Transcript, *, real_speech_seconds: float | None = None
) -> dict[str, float | int]:
    return {
        "words_total": words_total(transcript.text),
        "speech_rate_wpm": round(
            speech_rate_wpm(transcript, real_speech_seconds=real_speech_seconds), 1
        ),
    }
