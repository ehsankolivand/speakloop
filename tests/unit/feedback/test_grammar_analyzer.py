"""Free-form grammar analyzer (LLM stubbed).

Asserts the new contract: model returns its own `error_type` strings which
become `GrammarPattern.label`; verifies verbatim + coherence + no-op-fix
guards; checks deterministic rank by `(-occurrence_count, label)`. No live
model.
"""

from __future__ import annotations

import json

import pytest

from speakloop.asr import Transcript
from speakloop.feedback import grammar_analyzer
from speakloop.llm.interface import LLMEngineError

pytestmark = pytest.mark.unit


# A transcript triple with verbatim spans for the gold errors below.
TS = [
    Transcript(
        text="I like to programming every day at work here.",
        audio_duration_seconds=60.0,
    ),
    Transcript(
        text="I build payment systems for a fintech company.",
        audio_duration_seconds=45.0,
    ),
    Transcript(
        text="Honestly I enjoy to build reliable services.",
        audio_duration_seconds=30.0,
    ),
]


class _StubLLM:
    def __init__(self, response: str) -> None:
        self._r = response
        self.calls = 0

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        self.calls += 1
        return self._r


def _err(ord_: int, quote: str, corrected: str, error_type: str, explanation: str) -> dict:
    return {
        "attempt_ordinal": ord_,
        "quote": quote,
        "corrected": corrected,
        "error_type": error_type,
        "explanation": explanation,
    }


def _payload(*errors: dict) -> str:
    return json.dumps({"errors": list(errors)})


# --- Label = model's error_type, grouping, rank ------------------------------


def test_free_form_label_becomes_pattern_label():
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "gerund/infinitive confusion",
             "After 'like', use the -ing form.")
    )
    patterns = grammar_analyzer.analyze(TS, _StubLLM(payload))
    assert len(patterns) == 1
    assert patterns[0].label == "gerund/infinitive confusion"
    assert patterns[0].explanation == "After 'like', use the -ing form."
    assert patterns[0].occurrence_count == 1
    assert patterns[0].impact_rank == 1
    assert patterns[0].catalog_id is None  # free-form world


def test_multiple_errors_same_type_group_into_one_pattern():
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "gerund/infinitive confusion",
             "After 'like', use the -ing form."),
        _err(3, "enjoy to build", "enjoy building",
             "gerund/infinitive confusion",
             "After 'enjoy', use the -ing form."),
    )
    patterns = grammar_analyzer.analyze(TS, _StubLLM(payload))
    assert len(patterns) == 1
    p = patterns[0]
    assert p.label == "gerund/infinitive confusion"
    assert p.occurrence_count == 2
    assert len(p.evidence) == 2
    # Explanation uses the FIRST item's wording (representative).
    assert p.explanation == "After 'like', use the -ing form."


def test_multiple_distinct_types_yield_distinct_patterns_with_contiguous_ranks():
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "gerund/infinitive confusion", "Use -ing after like."),
        _err(2, "build payment", "build payments",
             "missing plural -s", "After 'build', the noun should be plural."),
        _err(3, "enjoy to build", "enjoy building",
             "gerund/infinitive confusion", "Use -ing after enjoy."),
    )
    patterns = grammar_analyzer.analyze(TS, _StubLLM(payload))
    assert len(patterns) == 2
    # Ranks are contiguous 1..N (no gaps).
    assert {p.impact_rank for p in patterns} == {1, 2}
    # The two-occurrence pattern outranks the one-occurrence pattern.
    by_rank = {p.impact_rank: p for p in patterns}
    assert by_rank[1].label == "gerund/infinitive confusion"
    assert by_rank[1].occurrence_count == 2
    assert by_rank[2].label == "missing plural -s"
    assert by_rank[2].occurrence_count == 1


def test_impact_rank_ties_break_alphabetically():
    # Two distinct error_types with the same occurrence_count (1 each); the
    # quotes are coherence-safe substrings of TS[0] and TS[1].
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "z-type error", "Reason z."),
        _err(2, "build payment", "build payments",
             "a-type error", "Reason a."),
    )
    patterns = grammar_analyzer.analyze(TS, _StubLLM(payload))
    assert len(patterns) == 2
    # Same occurrence_count (1 each) → alpha tiebreak: "a-type" before "z-type".
    by_rank = sorted(patterns, key=lambda p: p.impact_rank)
    assert by_rank[0].label == "a-type error"
    assert by_rank[1].label == "z-type error"


# --- Verification gates (verbatim, coherence, no-op fix) ---------------------


def test_non_verbatim_quote_is_dropped():
    payload = _payload(
        _err(1, "this exact phrase is not in the transcript",
             "this exact phrase is not in the transcript fixed",
             "some-type", "some reason."),
    )
    assert grammar_analyzer.analyze(TS, _StubLLM(payload)) == []


def test_no_op_fix_is_dropped():
    payload = _payload(
        _err(1, "like to programming", "like to programming",
             "gerund/infinitive confusion", "no-op."),
    )
    # corrected == quote → not a real fix → dropped.
    assert grammar_analyzer.analyze(TS, _StubLLM(payload)) == []


def test_invalid_attempt_ordinal_is_dropped():
    payload = _payload(
        _err(99, "like to programming", "like programming",
             "gerund/infinitive confusion", "out of range."),
    )
    assert grammar_analyzer.analyze(TS, _StubLLM(payload)) == []


def test_missing_error_type_is_dropped():
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "", "no error_type."),
    )
    assert grammar_analyzer.analyze(TS, _StubLLM(payload)) == []


def test_missing_explanation_is_dropped():
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "gerund/infinitive confusion", ""),
    )
    assert grammar_analyzer.analyze(TS, _StubLLM(payload)) == []


def test_empty_errors_yields_empty_patterns():
    assert grammar_analyzer.analyze(TS, _StubLLM(json.dumps({"errors": []}))) == []


def test_empty_transcripts_yields_empty_patterns():
    # Short-circuit before LLM call.
    llm = _StubLLM(_payload())
    assert grammar_analyzer.analyze([], llm) == []
    assert llm.calls == 0


# --- Recovery / bounded regenerate -------------------------------------------


def test_malformed_response_raises_after_bounded_regenerate():
    """Persistent junk → one bounded regenerate → graceful LLMEngineError."""

    class _LLM:
        def __init__(self):
            self.calls = 0

        def generate(self, *_a, **_k):
            self.calls += 1
            return "not json at all"

    llm = _LLM()
    with pytest.raises(LLMEngineError):
        grammar_analyzer.analyze(TS, llm)
    assert llm.calls == 2  # original + one bounded regenerate, then raise


# --- Evidence shape (verbatim + corrected, no catalog_id) --------------------


def test_evidence_carries_attempt_quote_and_corrected_only():
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "gerund/infinitive confusion", "Use -ing after like."),
    )
    patterns = grammar_analyzer.analyze(TS, _StubLLM(payload))
    ev = patterns[0].evidence[0]
    assert set(ev.keys()) == {"attempt_ordinal", "quote", "corrected"}
    assert ev["attempt_ordinal"] == 1
    assert ev["quote"] == "like to programming"
    assert ev["corrected"] == "like programming"


def test_suggested_fix_is_none_for_free_form_patterns():
    payload = _payload(
        _err(1, "like to programming", "like programming",
             "gerund/infinitive confusion", "Use -ing."),
    )
    patterns = grammar_analyzer.analyze(TS, _StubLLM(payload))
    assert patterns[0].suggested_fix is None


# --- 008: additive `system_prompt` override (cloud mode) --------------------


class _CapturingLLM:
    """Stub that records the system prompt it was handed."""

    def __init__(self, response: str) -> None:
        self._r = response
        self.system_prompts: list[str] = []

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        self.system_prompts.append(system_prompt)
        return self._r


def test_analyze_defaults_to_local_system_prompt():
    llm = _CapturingLLM(_payload())
    grammar_analyzer.analyze(TS, llm)
    assert llm.system_prompts == [grammar_analyzer._SYSTEM_PROMPT]


def test_analyze_forwards_explicit_system_prompt():
    llm = _CapturingLLM(_payload())
    grammar_analyzer.analyze(TS, llm, system_prompt="CLOUD-PROMPT")
    assert llm.system_prompts == ["CLOUD-PROMPT"]
    assert grammar_analyzer._SYSTEM_PROMPT not in llm.system_prompts


def test_explicit_system_prompt_used_on_bounded_regenerate():
    # A repetition-loop raw triggers ONE regenerate; both passes must use the
    # supplied cloud prompt, never the local one. Unparseable both times → the
    # existing terminal LLMEngineError is raised after the two attempts.
    looping = " ".join(["word"] * 12)  # trips _looks_like_repetition_loop
    llm = _CapturingLLM(looping)
    with pytest.raises(LLMEngineError):
        grammar_analyzer.analyze(TS, llm, system_prompt="CLOUD-PROMPT")
    assert llm.system_prompts == ["CLOUD-PROMPT", "CLOUD-PROMPT"]
