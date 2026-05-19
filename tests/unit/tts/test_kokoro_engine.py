"""T040 — Kokoro engine wrapper hits cache on repeat calls and wraps engine errors."""

from __future__ import annotations

import shutil

import pytest

from speakloop.tts.interface import TTSEngineError
from speakloop.tts.kokoro_engine import KokoroEngine

pytestmark = pytest.mark.unit


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(tmp_path / "tts"))
    yield tmp_path / "tts"


class _StubTTS:
    """Test double for the underlying KokoroTTS instance."""

    def __init__(self, fixture_wav, *, fail: bool = False) -> None:
        self._wav = fixture_wav
        self._fail = fail
        self.save_calls = []

    def save(self, text, path, voice="af_heart", speed=1.0, sample_rate=24000, language=None):
        self.save_calls.append((text, path, voice))
        if self._fail:
            raise RuntimeError("engine exploded")
        # The real KokoroTTS.save writes the WAV to `path`. We satisfy that
        # contract by copying a fixture WAV into place.
        shutil.copyfile(self._wav, path)

    def list_voices(self):
        return ["af_heart", "bm_george"]


def test_synthesize_uses_cached_path_on_repeat(monkeypatch, tmp_cache_dir, wav_fixture):
    stub = _StubTTS(wav_fixture("test-clip.wav"))
    engine = KokoroEngine()
    monkeypatch.setattr(engine, "_load", lambda: stub)

    p1 = engine.synthesize("hello", voice="bm_george")
    p2 = engine.synthesize("hello", voice="bm_george")
    assert p1 == p2
    assert len(stub.save_calls) == 1  # second call hit the cache


def test_synthesize_empty_text_raises():
    engine = KokoroEngine()
    with pytest.raises(TTSEngineError):
        engine.synthesize("   ")


def test_engine_failure_wrapped(monkeypatch, tmp_cache_dir, wav_fixture):
    stub = _StubTTS(wav_fixture("test-clip.wav"), fail=True)
    engine = KokoroEngine()
    monkeypatch.setattr(engine, "_load", lambda: stub)

    with pytest.raises(TTSEngineError):
        engine.synthesize("hello")


def test_available_voices_falls_back_when_engine_unloadable(monkeypatch):
    """When the model isn't downloaded, available_voices returns a static list."""
    engine = KokoroEngine()

    def boom():
        raise TTSEngineError("not installed")

    monkeypatch.setattr(engine, "_load", boom)
    voices = engine.available_voices()
    assert "af_heart" in voices
    assert isinstance(voices, list)
