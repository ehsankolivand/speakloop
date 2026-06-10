"""Artifact consistency-checker tests (010-interview-loop, T026).

Recorded-fixture fakes for the LLM (no live calls). Asserts the deterministic
resolution: a consistent artifact is kept, a contradiction with a correction is
replaced, a contradiction without a correction is dropped, and a failed check
withholds the artifact (SC-004 — no contradiction ever survives to the report).
"""

from __future__ import annotations

import pytest

from speakloop.llm import LLMEngineError
from speakloop.triage import consistency

pytestmark = pytest.mark.unit

_IDEAL = "An ANR fires after 5 seconds; Android 12 made trace collection cheaper."


class _FakeLLM:
    """Returns a recorded JSON response, or raises to simulate an unavailable model."""

    def __init__(self, response: str | None = None, *, error: bool = False):
        self._response = response
        self._error = error

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        if self._error:
            raise LLMEngineError("model unavailable")
        return self._response


_CONSISTENT = '{"consistent": true, "contradictions": [], "corrected": null}'
_CORRECTABLE = (
    '{"consistent": false, '
    '"contradictions": [{"claim": "Android 11", "ideal_claim": "Android 12"}], '
    '"corrected": "Android 12 made trace collection cheaper."}'
)
_DROP = (
    '{"consistent": false, '
    '"contradictions": [{"claim": "throws NullPointerException", "ideal_claim": "IllegalStateException"}], '
    '"corrected": null}'
)


def test_consistent_artifact_is_kept_unchanged():
    verdict = consistency.check_artifact("Move work off the main thread.", _IDEAL,
                                         _FakeLLM(_CONSISTENT), system_prompt="sp")
    assert verdict.consistent is True
    assert consistency.resolve("Move work off the main thread.", verdict) == "Move work off the main thread."


def test_contradiction_with_correction_is_replaced():
    artifact = "Android 11 made trace collection cheaper."
    verdict = consistency.check_artifact(artifact, _IDEAL, _FakeLLM(_CORRECTABLE), system_prompt="sp")
    assert verdict.consistent is False
    assert consistency.resolve(artifact, verdict) == "Android 12 made trace collection cheaper."


def test_contradiction_without_correction_is_dropped():
    artifact = "It throws NullPointerException."
    verdict = consistency.check_artifact(artifact, _IDEAL, _FakeLLM(_DROP), system_prompt="sp")
    assert verdict.consistent is False
    assert consistency.resolve(artifact, verdict) is None


def test_unavailable_model_withholds_the_artifact():
    verdict = consistency.check_artifact("anything", _IDEAL, _FakeLLM(error=True), system_prompt="sp")
    assert verdict.withheld is True
    assert consistency.resolve("anything", verdict) is None


def test_unparseable_output_withholds_the_artifact():
    verdict = consistency.check_artifact("anything", _IDEAL, _FakeLLM("not json at all"),
                                         system_prompt="sp")
    assert verdict.withheld is True
    assert consistency.resolve("anything", verdict) is None
