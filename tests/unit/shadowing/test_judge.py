"""T029 (018, US2) — content-word completeness judging of a spoken repeat."""

from __future__ import annotations

import pytest

from speakloop.shadowing.judge import judge_completeness

pytestmark = pytest.mark.unit


def test_covered_and_missed_content_words():
    r = judge_completeness("The system creates a new Activity instance.", "the system creates a new instance")
    assert set(r.covered) == {"system", "creates", "new", "instance"}
    assert r.missed == ("activity",)
    assert r.captured is True
    assert r.coverage == pytest.approx(4 / 5)


def test_function_words_are_excluded_from_content():
    r = judge_completeness("It is on the stack.", "yes it is on the stack")
    assert r.content_words == ("stack",)  # the/it/is/on excluded
    assert r.covered == ("stack",)


def test_empty_repeat_is_not_captured():
    r = judge_completeness("The window is detached.", "   ")
    assert r.captured is False
    assert r.coverage == 0.0
    assert set(r.missed) == {"window", "detached"}


def test_full_coverage_is_flagged_strong():
    r = judge_completeness("Cache the result.", "we cache the result quickly")
    assert r.coverage == 1.0
    assert r.is_strong is True


def test_low_coverage_is_not_strong_but_still_captured():
    r = judge_completeness("Detach the window view hierarchy now.", "detach")
    assert r.captured is True
    assert r.is_strong is False


def test_deterministic_for_a_fixed_transcript():
    a = judge_completeness("Detach the window hierarchy.", "detach window")
    b = judge_completeness("Detach the window hierarchy.", "detach window")
    assert a == b


def test_only_stopwords_sentence_is_trivially_complete_when_something_said():
    r = judge_completeness("It is what it is.", "yes indeed")
    assert r.content_words == ()
    assert r.coverage == 1.0 and r.captured is True
