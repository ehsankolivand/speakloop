"""Pause metric (FR-012b). 250 ms threshold — the single configurable knob."""

from __future__ import annotations

from speakloop.asr import WordTiming

PAUSE_THRESHOLD_MS = 250


def _within_regions(start: float, end: float, regions: tuple[tuple[float, float], ...]) -> bool:
    """True if the gap interval [start, end] lies fully inside one speech region."""
    return any(r0 <= start and end <= r1 for (r0, r1) in regions)


def _gaps_ms(
    words: list[WordTiming], *, vad_regions: tuple[tuple[float, float], ...] | None = None
) -> list[float]:
    """Return inter-word gap durations in milliseconds, in order.

    ``vad_regions`` (010, P4): when supplied, a gap is counted only if it lies
    inside a single real-speech region — so a gap spanning a dropped
    silence/hallucination span is not mistaken for a thinking pause. ``None`` ⇒
    original behaviour (every positive gap).
    """
    gaps: list[float] = []
    for prev, cur in zip(words, words[1:]):
        gap = (cur.start_seconds - prev.end_seconds) * 1000.0
        if gap <= 0:
            continue
        if vad_regions and not _within_regions(prev.end_seconds, cur.start_seconds, vad_regions):
            continue
        gaps.append(gap)
    return gaps


def compute(
    words: list[WordTiming],
    *,
    threshold_ms: float = PAUSE_THRESHOLD_MS,
    vad_regions: tuple[tuple[float, float], ...] | None = None,
) -> dict[str, float | int]:
    if not words or len(words) < 2:
        return {"pauses_count": 0, "mean_pause_ms": 0.0}

    pauses = [g for g in _gaps_ms(words, vad_regions=vad_regions) if g >= threshold_ms]
    if not pauses:
        return {"pauses_count": 0, "mean_pause_ms": 0.0}

    return {
        "pauses_count": len(pauses),
        "mean_pause_ms": round(sum(pauses) / len(pauses), 1),
    }
