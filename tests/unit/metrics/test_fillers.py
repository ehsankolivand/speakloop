"""T055 — fillers metric (FR-012a)."""

from __future__ import annotations

import pytest

from speakloop.metrics import fillers

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "tok", ["um", "uh", "ah", "er", "hmm", "like", "you know", "i mean", "basically", "actually"]
)
def test_canonical_tokens_detected_case_insensitively(tok):
    text = f"so {tok.upper()} the answer is twelve"
    assert fillers.filler_words_count(text) >= 1


def test_likely_does_not_match_like():
    assert fillers.filler_words_count("It is likely true.") == 0


def test_multiword_phrases_match_as_phrases():
    text = "I mean, you know, the system is good."
    assert fillers.filler_words_count(text) == 2


def test_density_formula():
    text = "um one two three four five"  # 1 filler / 6 word tokens
    d = fillers.filler_density_per_100_words(text)
    assert d == pytest.approx(100 / 6, rel=0.01)


def test_density_zero_words():
    assert fillers.filler_density_per_100_words("") == 0.0
