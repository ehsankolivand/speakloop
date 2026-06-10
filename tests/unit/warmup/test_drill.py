"""Warm-up drill tests (010-interview-loop, P2c) — deterministic judge + faked gen."""

from __future__ import annotations

import pytest

from speakloop.warmup import drill

pytestmark = pytest.mark.unit

_ITEM = drill.DrillItem(
    target_sentence="You must restart the service.",
    corrected_form="must restart",
    error_form="must restarting",
)


def test_judge_pass_when_corrected_present_and_error_absent():
    assert drill.judge_item(_ITEM, "Yes, you must restart the service now.") == "pass"


def test_judge_fail_when_error_form_present():
    assert drill.judge_item(_ITEM, "You must restarting the service.") == "fail"


def test_judge_fail_when_corrected_absent():
    assert drill.judge_item(_ITEM, "You should reboot the service.") == "fail"


def test_judge_incomplete_on_silence_or_garbage():
    assert drill.judge_item(_ITEM, "") == "incomplete"
    assert drill.judge_item(_ITEM, "uh") == "incomplete"


class _FakeLLM:
    def __init__(self, response):
        self._r = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        return self._r


def test_generate_drill_parses_three_items():
    resp = (
        '{"items": ['
        '{"target_sentence": "You must restart it.", "corrected_form": "must restart", "error_form": "must restarting"},'
        '{"target_sentence": "We must handle the error.", "corrected_form": "must handle", "error_form": "must handling"},'
        '{"target_sentence": "It must run on the main thread.", "corrected_form": "must run", "error_form": "must running"}]}'
    )
    items = drill.generate_drill("modal + base verb", _FakeLLM(resp), system_prompt="sp")
    assert len(items) == 3
    assert items[0].corrected_form == "must restart"


def test_generate_drill_raises_on_empty():
    from speakloop.llm import LLMEngineError

    with pytest.raises(LLMEngineError):
        drill.generate_drill("x", _FakeLLM("  "), system_prompt="sp")
