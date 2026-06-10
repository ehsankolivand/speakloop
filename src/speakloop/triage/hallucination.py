"""Deterministic ASR-hallucination filter (010-interview-loop, P4).

Runs BEFORE grammar/coverage/metrics and drops transcript spans that are ASR
hallucinations, using only signals the engine already produced — VAD-silence
overlap, Whisper's own decode guards (``no_speech_prob`` / ``avg_logprob`` /
``compression_ratio``), and a curated phantom-phrase list. No language model is
involved, so the guarantee "no hallucination text ever reaches grammar evidence"
(SC-003 / FR-028) holds even offline and even when the LLM is the analyzer.

This module imports no engine package (Principle V); it consumes the additive
signals surfaced on ``asr.Transcript`` (``segments`` / ``vad_regions``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from speakloop.asr import Transcript

# Whisper's own internal decode-guard thresholds (whisper_mlx_engine decode opts),
# reused here as the post-hoc hallucination signals they were designed to be.
NO_SPEECH_PROB_MAX = 0.6
AVG_LOGPROB_MIN = -1.0
COMPRESSION_RATIO_MAX = 2.4

_PHANTOM_FILE = Path(__file__).parent / "phantom_phrases.txt"
_PUNCT_RE = re.compile(r"[^a-z0-9' ]+")
_WS_RE = re.compile(r"\s+")

SpanClass = Literal["real", "mishearing", "hallucination"]


@dataclass(frozen=True)
class TriagedSpan:
    """One classified transcript span."""

    text: str
    start_seconds: float
    end_seconds: float
    span_class: SpanClass
    signal: str
    heard: str | None = None
    likely_intended: str | None = None


@dataclass
class TriageResult:
    """Outcome of triage over one attempt transcript."""

    real_text: str
    real_regions: tuple[tuple[float, float], ...] = ()
    pronunciation_flags: list[TriagedSpan] = field(default_factory=list)
    dropped: list[TriagedSpan] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "real": len(self.real_regions),
            "mishearing": len(self.pronunciation_flags),
            "hallucination_dropped": len(self.dropped),
        }


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", (text or "").lower())).strip()


@lru_cache(maxsize=1)
def _phantom_phrases() -> tuple[str, ...]:
    if not _PHANTOM_FILE.exists():
        return ()
    out: list[str] = []
    for line in _PHANTOM_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(_normalize(line))
    return tuple(p for p in out if p)


def _matches_phantom(normalized: str) -> bool:
    if not normalized:
        return True  # an empty/punctuation-only segment is non-speech
    for phrase in _phantom_phrases():
        if normalized == phrase:
            return True
        # whole-phrase substring (word-boundary padded) so "subscribe" inside a
        # real sentence doesn't trip, but "please subscribe to the channel" does.
        if f" {phrase} " in f" {normalized} ":
            return True
    return False


def classify_segment(
    text: str,
    *,
    no_speech_prob: float | None = None,
    avg_logprob: float | None = None,
    compression_ratio: float | None = None,
    vad_silence: bool = False,
) -> tuple[SpanClass, str]:
    """Classify one segment from its recorded signals (deterministic).

    Returns ``(span_class, signal)`` where ``signal`` names the deciding rule.
    Only ``real`` and ``hallucination`` are produced here; mishearing is an
    LLM-assisted step layered on top (``triage/mishearing.py``).
    """
    normalized = _normalize(text)
    if _matches_phantom(normalized):
        return "hallucination", "phantom_phrase"
    if vad_silence:
        return "hallucination", "vad_silence"
    if no_speech_prob is not None and no_speech_prob >= NO_SPEECH_PROB_MAX:
        return "hallucination", f"no_speech_prob={no_speech_prob:.2f}"
    if avg_logprob is not None and avg_logprob <= AVG_LOGPROB_MIN:
        return "hallucination", f"avg_logprob={avg_logprob:.2f}"
    if compression_ratio is not None and compression_ratio >= COMPRESSION_RATIO_MAX:
        return "hallucination", f"compression_ratio={compression_ratio:.2f}"
    return "real", "real_speech"


def _overlaps_speech(
    start: float, end: float, vad_regions: tuple[tuple[float, float], ...]
) -> bool:
    """True if [start, end] overlaps any VAD speech region (so it is NOT silence)."""
    return any(start < r1 and r0 < end for (r0, r1) in vad_regions)


def filter_hallucinations(transcript: Transcript) -> TriageResult:
    """Drop hallucinated segments from a transcript (deterministic, no LLM).

    When the transcript carries no per-segment metadata (e.g. the Parakeet path,
    which does not hallucinate on silence — see asr/CLAUDE.md), this is a no-op:
    the full text is returned as real with no drops, preserving pre-feature
    behaviour.
    """
    if not transcript.segments:
        return TriageResult(real_text=transcript.text, real_regions=transcript.vad_regions)

    real_parts: list[str] = []
    real_regions: list[tuple[float, float]] = []
    dropped: list[TriagedSpan] = []
    for seg in transcript.segments:
        vad_silence = bool(transcript.vad_regions) and not _overlaps_speech(
            seg.start_seconds, seg.end_seconds, transcript.vad_regions
        )
        span_class, signal = classify_segment(
            seg.text,
            no_speech_prob=seg.no_speech_prob,
            avg_logprob=seg.avg_logprob,
            compression_ratio=seg.compression_ratio,
            vad_silence=vad_silence,
        )
        if span_class == "hallucination":
            dropped.append(
                TriagedSpan(
                    text=seg.text,
                    start_seconds=seg.start_seconds,
                    end_seconds=seg.end_seconds,
                    span_class="hallucination",
                    signal=signal,
                )
            )
        else:
            real_parts.append(seg.text.strip())
            real_regions.append((seg.start_seconds, seg.end_seconds))

    return TriageResult(
        real_text=" ".join(p for p in real_parts if p).strip(),
        real_regions=tuple(real_regions),
        dropped=dropped,
    )
