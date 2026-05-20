"""Contract test for the ASR engine Protocol shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.asr import (
    ASREngine,
    ASREngineError,
    Transcript,
    TranscriptionContext,
    WordTiming,
)

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
        self.loaded = False
        self.last_context: TranscriptionContext | None = None

    def transcribe(
        self,
        wav_path: Path,
        *,
        context: TranscriptionContext | None = None,
    ) -> Transcript:
        self.last_context = context
        return self._t

    def ensure_loaded(self) -> None:
        self.loaded = True


def test_stub_satisfies_asr_protocol(wav_fixture):
    wav = wav_fixture("attempt-short.wav")
    t = Transcript(text="x", words=[WordTiming("x", 0.0, 0.1)], audio_duration_seconds=0.1)
    engine: ASREngine = StubASREngine(t)
    # Existing call style (no context) still works — additive compatibility.
    assert engine.transcribe(wav) is t


def test_transcribe_accepts_optional_context(wav_fixture):
    wav = wav_fixture("attempt-short.wav")
    t = Transcript(text="x", words=[], audio_duration_seconds=0.1)
    engine = StubASREngine(t)
    ctx = TranscriptionContext(initial_prompt="coroutines threads", initial_prompt_sha256="ab", use_vad=True)
    assert engine.transcribe(wav, context=ctx) is t
    assert engine.last_context is ctx


def test_protocol_declares_ensure_loaded(wav_fixture):
    engine: ASREngine = StubASREngine(Transcript(text=""))
    engine.ensure_loaded()
    assert engine.loaded is True


def test_transcription_context_defaults():
    ctx = TranscriptionContext()
    assert ctx.initial_prompt is None
    assert ctx.initial_prompt_sha256 == ""
    assert ctx.use_vad is True


def test_asr_engine_error_is_exception():
    assert issubclass(ASREngineError, Exception)
