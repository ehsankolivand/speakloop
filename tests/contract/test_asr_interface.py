"""Contract test for the ASR engine Protocol shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.asr import ASREngine, ASREngineError, Transcript, WordTiming

pytestmark = pytest.mark.contract


def test_empty_transcript_is_empty():
    t = Transcript(text="", words=[], audio_duration_seconds=0.0)
    assert t.is_empty is True


def test_nonempty_transcript_is_not_empty():
    t = Transcript(
        text="hello world",
        words=[WordTiming("hello", 0.0, 0.5), WordTiming("world", 0.5, 1.0)],
        audio_duration_seconds=1.0,
    )
    assert t.is_empty is False


class StubASREngine:
    def __init__(self, transcript: Transcript) -> None:
        self._t = transcript

    def transcribe(self, wav_path: Path) -> Transcript:
        return self._t


def test_stub_satisfies_asr_protocol(wav_fixture):
    wav = wav_fixture("attempt-short.wav")
    t = Transcript(text="x", words=[WordTiming("x", 0.0, 0.1)], audio_duration_seconds=0.1)
    engine: ASREngine = StubASREngine(t)
    assert engine.transcribe(wav) is t


def test_asr_engine_error_is_exception():
    assert issubclass(ASREngineError, Exception)
