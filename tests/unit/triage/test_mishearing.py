"""Mishearing classifier tests (010-interview-loop, T072) — recorded-fixture fake.

A flagged mishearing becomes a pronunciation flag, never a grammar error (FR-026).
Detection is enrichment: a down/failing model never raises into the loop.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from speakloop.llm import LLMEngineError
from speakloop.triage import mishearing

pytestmark = pytest.mark.unit

_MISHEARINGS = yaml.safe_load(
    (Path(__file__).parents[2] / "fixtures" / "triage" / "cases.yaml").read_text()
)["mishearing_cases"]


class _FakeLLM:
    def __init__(self, response=None, *, error=False):
        self._response = response
        self._error = error

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        if self._error:
            raise LLMEngineError("model unavailable")
        return self._response


def test_flags_recorded_mishearing():
    recorded = json.dumps(
        {"mishearings": [{"span_text": "you mouse handle", "heard": "mouse", "likely_intended": "must"}]}
    )
    flags = mishearing.detect_mishearings("you mouse handle the exception", _FakeLLM(recorded),
                                          system_prompt="sp")
    assert len(flags) == 1
    assert flags[0].span_class == "mishearing"
    assert (flags[0].heard, flags[0].likely_intended) == ("mouse", "must")


def test_identical_heard_and_intended_dropped():
    recorded = json.dumps({"mishearings": [{"heard": "destroyed", "likely_intended": "destroyed"}]})
    assert mishearing.detect_mishearings("the activity is destroyed", _FakeLLM(recorded), system_prompt="sp") == []


def test_no_model_returns_empty_never_raises():
    assert mishearing.detect_mishearings("anything", _FakeLLM(error=True), system_prompt="sp") == []


def test_unparseable_returns_empty():
    assert mishearing.detect_mishearings("anything", _FakeLLM("not json"), system_prompt="sp") == []


def test_empty_text_returns_empty():
    assert mishearing.detect_mishearings("   ", _FakeLLM("{}"), system_prompt="sp") == []


def test_fixture_labels_present():
    # sanity: the fixture distinguishes a mishearing from real speech
    labels = {c["label"] for c in _MISHEARINGS}
    assert "mishearing" in labels and "real" in labels
