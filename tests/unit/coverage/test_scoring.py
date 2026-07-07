"""Coverage scoring tests (010-interview-loop, T065) — recorded LLM-response fake.

Asserts the deterministic parse/aggregate/delta over the recorded fixture in
tests/fixtures/coverage/cases.yaml. No live LLM; no byte-exact golden file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from speakloop.asr import Transcript
from speakloop.coverage import scoring

pytestmark = pytest.mark.unit

_CASE = yaml.safe_load(
    (Path(__file__).parents[2] / "fixtures" / "coverage" / "cases.yaml").read_text()
)["cases"][0]


class _FakeLLM:
    def __init__(self, response: str):
        self._r = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        return self._r


def _run():
    llm = _FakeLLM(json.dumps(_CASE["recorded_llm_response"]))
    return scoring.score_coverage(
        _CASE["key_points"],
        [Transcript(text="t1"), Transcript(text="t2"), Transcript(text="t3")],
        _CASE["ideal_answer"],
        llm,
        system_prompt="sp",
        version=2,
    )


def test_aggregate_and_delta():
    result = _run()
    a1 = next(r for r in result.attempt_records if r["attempt_ordinal"] == 1)
    a3 = next(r for r in result.attempt_records if r["attempt_ordinal"] == 3)
    assert a1["aggregate"] == pytest.approx(_CASE["expected"]["attempt_1_aggregate"], abs=0.01)
    assert a3["aggregate"] == pytest.approx(_CASE["expected"]["attempt_3_aggregate"], abs=0.01)
    assert result.final_aggregate == pytest.approx(_CASE["expected"]["attempt_3_aggregate"], abs=0.01)


def test_content_error_count():
    result = _run()
    assert len(result.content_errors) == _CASE["expected"]["content_error_count"]
    assert result.content_errors[0]["learner_claim"] == "Android 11"


def test_version_recorded_on_records():
    result = _run()
    assert all(r["key_points_version"] == 2 for r in result.attempt_records)


def test_missing_ids_default_to_missed():
    """A coverage response omitting a key-point id defaults that point to missed."""
    llm = _FakeLLM('{"attempts": [{"ordinal": 1, "coverage": [{"id": 1, "state": "covered"}]}], "content_errors": []}')
    result = scoring.score_coverage(
        [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}],
        [Transcript(text="t")], "ideal", llm, system_prompt="sp", version=1,
    )
    states = {pp["id"]: pp["state"] for pp in result.attempt_records[0]["per_point"]}
    assert states == {1: "covered", 2: "missed"}


def test_capitalized_states_are_normalized_not_downgraded():
    """A capitalized-but-valid state (e.g. the model emits "Covered"/"Partial") must be
    normalized, not silently coerced to "missed" (which would drop it from the aggregate)."""
    llm = _FakeLLM(
        '{"attempts": [{"ordinal": 1, "coverage": '
        '[{"id": 1, "state": "Covered"}, {"id": 2, "state": "Partial"}]}], "content_errors": []}'
    )
    result = scoring.score_coverage(
        [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}],
        [Transcript(text="t")], "ideal", llm, system_prompt="sp", version=1,
    )
    states = {pp["id"]: pp["state"] for pp in result.attempt_records[0]["per_point"]}
    assert states == {1: "covered", 2: "partial"}
    assert result.attempt_records[0]["aggregate"] == 0.75  # (1 + 0.5) / 2, not 0.0


def test_coverage_recovers_after_one_bounded_retry():
    """IMP-011: a transient unparseable first response is recovered by one bounded
    regenerate instead of discarding the whole (expensive) coverage result."""
    good = '{"attempts": [{"ordinal": 1, "coverage": [{"id": 1, "state": "covered"}]}], "content_errors": []}'

    class _FlakyLLM:
        def __init__(self):
            self.calls = 0

        def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
            self.calls += 1
            return "garbage no json" if self.calls == 1 else good

    llm = _FlakyLLM()
    result = scoring.score_coverage(
        [{"id": 1, "text": "a"}], [Transcript(text="t")], "ideal", llm, system_prompt="sp", version=1,
    )
    assert llm.calls == 2  # first pass failed to parse, the bounded retry recovered it
    assert result.attempt_records[0]["per_point"][0]["state"] == "covered"


def test_non_numeric_ordinal_or_id_skipped_not_crashing():
    """IMP-005: a non-numeric attempt ordinal / coverage id from the model must not crash
    the whole coverage pass — skip just the malformed attempt / coverage entry."""
    llm = _FakeLLM(
        '{"attempts": ['
        '{"ordinal": 1, "coverage": [{"id": 1, "state": "covered"}, {"id": "oops", "state": "covered"}]},'
        '{"ordinal": "n/a", "coverage": [{"id": 1, "state": "covered"}]}'
        '], "content_errors": []}'
    )
    result = scoring.score_coverage(
        [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}],
        [Transcript(text="t")], "ideal", llm, system_prompt="sp", version=1,
    )
    # The non-numeric-ordinal attempt is dropped; the valid one survives.
    assert [r["attempt_ordinal"] for r in result.attempt_records] == [1]
    states = {pp["id"]: pp["state"] for pp in result.attempt_records[0]["per_point"]}
    # Point 1 scored covered; the malformed-id entry was skipped so point 2 stays missed.
    assert states == {1: "covered", 2: "missed"}
