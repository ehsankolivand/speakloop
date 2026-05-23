"""T-G3 — bounded regenerate on repetition-loop / truncation (grammar-output-schema §C).

A repetition-loop (or length-truncated) first response triggers EXACTLY ONE bounded
regenerate; then the analysis either succeeds or falls back cleanly to today's graceful
path (LLMEngineError → phase_c_error → Phase-B report). The retry is bounded so a bad
session can never hang (FR-002, FR-003). No live model — a sequence stub LLM.
"""

from __future__ import annotations

import json

import pytest

from speakloop.asr import Transcript
from speakloop.feedback import grammar_analyzer as ga
from speakloop.llm.interface import LLMEngineError

pytestmark = pytest.mark.unit

TS = [Transcript(text="I like to programming every day at work here.", audio_duration_seconds=60.0)]

GOOD = (
    '{"patterns": [{"label": "gerund/infinitive confusion", "occurrence_count": 2, '
    '"evidence": [{"attempt_ordinal": 1, "quote": "like to programming", '
    '"corrected": "like programming"}]}]}'
)
# A degenerate repetition loop: the same token many times in a row (the classic
# 4-bit stuck-loop), unparseable as JSON.
LOOP = "The recurring pattern is " + ("stop " * 30)
# Pure prose, no JSON at all → unrecoverable (but not a token loop).
JUNK = "I am sorry, I cannot help with that request right now. " * 12


class _SequenceLLM:
    """Returns responses[call_index]; clamps to the last entry."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False, **kw):
        self.calls += 1
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


def test_repetition_loop_helper_detects_loops_and_passes_clean_text():
    assert ga._looks_like_repetition_loop(LOOP) is True
    assert ga._looks_like_repetition_loop(GOOD) is False
    assert ga._looks_like_repetition_loop("A short normal sentence about coroutines.") is False
    assert ga._looks_like_repetition_loop("") is False


def test_loop_then_clean_triggers_exactly_one_regenerate():
    llm = _SequenceLLM([LOOP, GOOD])
    patterns = ga.analyze(TS, llm)
    assert llm.calls == 2  # one original + exactly one regenerate
    assert patterns and patterns[0].catalog_id == "gerund-infinitive-confusion"


def test_clean_first_response_does_not_regenerate():
    llm = _SequenceLLM([GOOD, GOOD])
    patterns = ga.analyze(TS, llm)
    assert llm.calls == 1  # no regenerate when the first parse is clean and non-looping
    assert patterns


def test_two_failures_fall_back_cleanly_without_hang():
    llm = _SequenceLLM([JUNK, JUNK])
    with pytest.raises(LLMEngineError):
        ga.analyze(TS, llm)
    assert llm.calls == 2  # bounded: original + one regenerate, then graceful fallback


def test_regenerate_is_bounded_to_one_even_on_persistent_loop():
    llm = _SequenceLLM([LOOP, LOOP, LOOP])
    with pytest.raises(LLMEngineError):
        ga.analyze(TS, llm)
    assert llm.calls == 2  # never more than two total calls (no hang)
