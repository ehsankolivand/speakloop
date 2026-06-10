"""Deterministic hallucination-filter tests (010-interview-loop, T025).

Table-driven over the recorded, human-labelled fixtures in
tests/fixtures/triage/cases.yaml. Asserts classification from recorded VAD/Whisper
signals — never a byte-exact golden file. Backs SC-003 (no hallucination text ever
reaches grammar evidence) at the unit level.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from speakloop.asr import SegmentMeta, Transcript
from speakloop.triage import hallucination

pytestmark = pytest.mark.unit

_CASES = yaml.safe_load(
    (Path(__file__).parents[2] / "fixtures" / "triage" / "cases.yaml").read_text()
)
_HALLUCINATION_CASES = _CASES["hallucination_cases"]


@pytest.mark.parametrize("case", _HALLUCINATION_CASES, ids=lambda c: c["text"][:24])
def test_classify_segment_matches_label(case):
    span_class, signal = hallucination.classify_segment(
        case["text"],
        no_speech_prob=case.get("no_speech_prob"),
        avg_logprob=case.get("avg_logprob"),
        vad_silence=case.get("vad_silence", False),
    )
    assert span_class == case["label"], f"{case['text']!r} → {span_class} ({signal})"


def test_filter_drops_hallucinations_keeps_real():
    """filter_hallucinations removes hallucination segments, keeps real text."""
    segments = []
    for i, case in enumerate(_HALLUCINATION_CASES):
        segments.append(
            SegmentMeta(
                start_seconds=float(i),
                end_seconds=float(i) + 0.9,
                text=case["text"],
                avg_logprob=case.get("avg_logprob"),
                no_speech_prob=case.get("no_speech_prob"),
            )
        )
    transcript = Transcript(
        text=" ".join(c["text"] for c in _HALLUCINATION_CASES),
        segments=tuple(segments),
    )
    result = hallucination.filter_hallucinations(transcript)

    for case in _HALLUCINATION_CASES:
        if case["label"] == "hallucination":
            assert case["text"] not in result.real_text
        else:
            assert case["text"] in result.real_text
    assert len(result.dropped) == sum(
        1 for c in _HALLUCINATION_CASES if c["label"] == "hallucination"
    )


def test_no_segments_is_a_noop():
    """A transcript without per-segment metadata (e.g. Parakeet) is unchanged."""
    transcript = Transcript(text="the activity is destroyed on rotation")
    result = hallucination.filter_hallucinations(transcript)
    assert result.real_text == transcript.text
    assert result.dropped == []


def test_phantom_phrase_dropped_without_signals():
    """A phantom phrase is dropped even with no confidence signals at all."""
    span_class, signal = hallucination.classify_segment("Thanks for watching!")
    assert span_class == "hallucination"
    assert signal == "phantom_phrase"
