"""T053 — speech_rate metric."""

from __future__ import annotations

import pytest

from speakloop.asr import Transcript
from speakloop.metrics import speech_rate

pytestmark = pytest.mark.unit


def test_words_total_excludes_punctuation():
    assert speech_rate.words_total("hello, world!") == 2
    assert speech_rate.words_total(",,, ... !!!") == 0


def test_speech_rate_basic():
    t = Transcript(text="one two three four", words=[], audio_duration_seconds=60.0)
    assert speech_rate.speech_rate_wpm(t) == pytest.approx(4.0)


def test_zero_duration_is_zero_not_error():
    t = Transcript(text="a b c", words=[], audio_duration_seconds=0.0)
    assert speech_rate.speech_rate_wpm(t) == 0.0
