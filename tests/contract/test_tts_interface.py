"""Contract test for the TTS engine Protocol shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.tts import TTSEngine, TTSEngineError

pytestmark = pytest.mark.contract


class StubTTSEngine:
    def __init__(self, fixture_wav: Path) -> None:
        self._wav = fixture_wav

    def synthesize(self, text: str, voice: str | None = None) -> Path:
        return self._wav

    def available_voices(self) -> list[str]:
        return ["bm_george", "af_bella"]


def test_stub_satisfies_tts_protocol(wav_fixture):
    wav = wav_fixture("question-short.wav")
    engine: TTSEngine = StubTTSEngine(wav)
    assert engine.synthesize("hello") == wav
    assert "bm_george" in engine.available_voices()


def test_tts_engine_error_is_exception():
    assert issubclass(TTSEngineError, Exception)
    with pytest.raises(TTSEngineError):
        raise TTSEngineError("boom")
