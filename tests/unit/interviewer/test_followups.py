"""Follow-up generation tests (010-interview-loop, P1) with a recorded-fixture fake LLM.

Verifies the deterministic logic around the LLM call: the probe-worthiness gate
(FR-006), grounding in the learner's own words (SC-010), the 1–2 cap, and graceful
failure. The model itself is faked — no live calls.
"""

from __future__ import annotations

import pytest

from speakloop.asr import Transcript
from speakloop.interviewer import followups
from speakloop.llm import LLMEngineError

pytestmark = pytest.mark.unit


class _FakeLLM:
    def __init__(self, response: str):
        self._response = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        return self._response


# A real-speech answer well above the 30-word probe-worthiness threshold.
_RICH = [
    Transcript(text="When the device rotates the activity is destroyed and recreated by the system."),
    Transcript(text="The view model survives the configuration change because it is retained."),
    Transcript(text="I save the small UI state into the bundle inside on save instance state."),
]
_GROUNDED = (
    '{"followups": ['
    '{"question": "Why is the view model retained across the configuration change?", '
    '"probe_ref": "view model", "probe_type": "why"}, '
    '{"question": "What happens to the bundle if the process is killed?", '
    '"probe_ref": "bundle", "probe_type": "edge_case"}]}'
)


def test_two_grounded_followups_returned():
    out = followups.generate_followups("Walk me through rotation.", _RICH, _FakeLLM(_GROUNDED),
                                       system_prompt="sp")
    assert len(out) == 2
    assert out[0]["probe_type"] == "why"
    assert all(f["question"] for f in out)


def test_cap_respected():
    out = followups.generate_followups("Q", _RICH, _FakeLLM(_GROUNDED), system_prompt="sp", max_count=1)
    assert len(out) == 1


def test_probe_worthiness_gate_skips_short_answers():
    short = [Transcript(text="I don't know."), Transcript(text="Maybe."), Transcript(text="Pass.")]
    out = followups.generate_followups("Q", short, _FakeLLM(_GROUNDED), system_prompt="sp")
    assert out == []  # FR-006: too little material to probe → zero follow-ups


def test_ungrounded_followup_dropped():
    ungrounded = (
        '{"followups": [{"question": "Tell me about your weekend plans?", '
        '"probe_ref": "", "probe_type": "gap"}]}'
    )
    out = followups.generate_followups("Q", _RICH, _FakeLLM(ungrounded), system_prompt="sp")
    assert out == []  # SC-010: not grounded in the learner's words or a probe ref


def test_empty_response_raises():
    with pytest.raises(LLMEngineError):
        followups.generate_followups("Q", _RICH, _FakeLLM("   "), system_prompt="sp")


def test_unparseable_response_raises_valueerror():
    with pytest.raises(ValueError):
        followups.generate_followups("Q", _RICH, _FakeLLM("not json"), system_prompt="sp")
