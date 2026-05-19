"""Pause metric (FR-012b). 250 ms threshold — the single configurable knob."""

from __future__ import annotations

from speakloop.asr import WordTiming

PAUSE_THRESHOLD_MS = 250


def _gaps_ms(words: list[WordTiming]) -> list[float]:
    """Return inter-word gap durations in milliseconds, in order."""
    gaps: list[float] = []
    for prev, cur in zip(words, words[1:]):
        gap = (cur.start_seconds - prev.end_seconds) * 1000.0
        if gap > 0:
            gaps.append(gap)
    return gaps


def compute(
    words: list[WordTiming], *, threshold_ms: float = PAUSE_THRESHOLD_MS
) -> dict[str, float | int]:
    if not words or len(words) < 2:
        return {"pauses_count": 0, "mean_pause_ms": 0.0}

    pauses = [g for g in _gaps_ms(words) if g >= threshold_ms]
    if not pauses:
        return {"pauses_count": 0, "mean_pause_ms": 0.0}

    return {
        "pauses_count": len(pauses),
        "mean_pause_ms": round(sum(pauses) / len(pauses), 1),
    }
