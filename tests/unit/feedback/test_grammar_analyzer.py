"""T083 — grammar analyzer with mocked LLM produces verified evidence-backed findings."""

from __future__ import annotations

import json

import pytest

from speakloop.asr import Transcript
from speakloop.feedback import grammar_analyzer
from speakloop.llm.interface import LLMEngineError

pytestmark = pytest.mark.unit


def _transcripts():
    return [
        Transcript(
            text="Um so a coroutine is uh a lightweight thread that runs on dispatcher. "
            "He write a function. My friend brother work at Google.",
            audio_duration_seconds=10.0,
        ),
        Transcript(
            text="Coroutine is suspendable computation. It run on a dispatcher. "
            "The system handle thousands of coroutines.",
            audio_duration_seconds=10.0,
        ),
        Transcript(
            text="Coroutines are lightweight threads. A coroutine run on a dispatcher. "
            "I depend on this library. He listen to the music.",
            audio_duration_seconds=10.0,
        ),
    ]


class MockLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7):
        return self._response


def test_seed_pattern_surfaced_with_verbatim_evidence():
    payload = {
        "patterns": [
            {
                "label": "3rd-person singular -s drop",
                "occurrence_count": 4,
                "evidence": [
                    {"attempt_ordinal": 1, "quote": "He write a function"},
                    {"attempt_ordinal": 2, "quote": "It run on a dispatcher"},
                    {"attempt_ordinal": 3, "quote": "He listen to the music"},
                ],
                "suggested_fix": "He writes / it runs / he listens.",
            }
        ]
    }
    patterns = grammar_analyzer.analyze(_transcripts(), MockLLM(json.dumps(payload)))
    assert len(patterns) == 1
    assert "3rd-person" in patterns[0].label
    assert patterns[0].occurrence_count == 4
    assert all("quote" in ev for ev in patterns[0].evidence)


def test_unverifiable_quote_is_dropped():
    payload = {
        "patterns": [
            {
                "label": "3rd-person singular -s drop",
                "occurrence_count": 1,
                "evidence": [{"attempt_ordinal": 1, "quote": "this exact phrase does NOT appear"}],
            }
        ]
    }
    patterns = grammar_analyzer.analyze(_transcripts(), MockLLM(json.dumps(payload)))
    assert patterns == []


def test_open_bucket_requires_count_two():
    payload = {
        "patterns": [
            {
                "label": "imaginary novel pattern",
                "occurrence_count": 1,
                "evidence": [{"attempt_ordinal": 1, "quote": "Um so a coroutine"}],
            }
        ]
    }
    assert grammar_analyzer.analyze(_transcripts(), MockLLM(json.dumps(payload))) == []


def test_open_bucket_with_count_two_kept():
    payload = {
        "patterns": [
            {
                "label": "novel recurring pattern",
                "occurrence_count": 2,
                "evidence": [
                    {"attempt_ordinal": 1, "quote": "lightweight thread"},
                    {"attempt_ordinal": 3, "quote": "lightweight threads"},
                ],
            }
        ]
    }
    out = grammar_analyzer.analyze(_transcripts(), MockLLM(json.dumps(payload)))
    assert len(out) == 1


def test_think_tag_in_response_is_rejected():
    raw = "<think>nope</think>" + json.dumps({"patterns": []})

    class _LLM:
        def generate(self, *_a, **_k):
            return raw

    with pytest.raises(LLMEngineError):
        grammar_analyzer.analyze(_transcripts(), _LLM())


def test_malformed_response_raises():
    class _LLM:
        def generate(self, *_a, **_k):
            return "not json at all"

    with pytest.raises(LLMEngineError):
        grammar_analyzer.analyze(_transcripts(), _LLM())
