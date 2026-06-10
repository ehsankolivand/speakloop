"""Key-point derivation + content-versioning tests (010-interview-loop, T066)."""

from __future__ import annotations

import pytest

from speakloop.coverage import keypoints

pytestmark = pytest.mark.unit


class _FakeLLM:
    def __init__(self, response):
        self._r = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        return self._r


def test_hash_stable_under_whitespace_only_edits():
    a = keypoints.ideal_answer_hash("An ANR fires after 5 seconds.")
    b = keypoints.ideal_answer_hash("  An ANR   fires  after 5 seconds.  ")
    assert a == b  # whitespace-only edit does not re-version


def test_hash_changes_on_meaningful_edit():
    a = keypoints.ideal_answer_hash("Android 12 made traces cheaper.")
    b = keypoints.ideal_answer_hash("Android 13 made traces cheaper.")
    assert a != b


def test_derive_caps_at_seven_and_ids_sequential():
    resp = '{"key_points": ' + str(["p%d" % i for i in range(10)]).replace("'", '"') + "}"
    points = keypoints.derive_key_points("q", "ideal", "definition", _FakeLLM(resp), system_prompt="sp")
    assert len(points) == keypoints.MAX_POINTS
    assert [p["id"] for p in points] == list(range(1, keypoints.MAX_POINTS + 1))


def test_behavioral_uses_star_components_without_llm():
    # llm response is irrelevant; behavioral short-circuits to STAR
    points = keypoints.derive_key_points("q", "ideal", "behavioral", _FakeLLM("ignored"), system_prompt="sp")
    assert [p["text"] for p in points] == list(keypoints.STAR_COMPONENTS)


def test_empty_response_raises():
    from speakloop.llm import LLMEngineError

    with pytest.raises(LLMEngineError):
        keypoints.derive_key_points("q", "ideal", "definition", _FakeLLM("  "), system_prompt="sp")
