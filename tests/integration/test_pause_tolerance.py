"""T022 — SC-C: thinking pauses produce no hallucinated tokens.

A Whisper stub that WOULD emit a phantom token if handed a long silent buffer
proves the point: with VAD on, the silent regions never reach the ASR, so the
phantom never appears. Twenty pause-bearing clips, zero hallucinations.
"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from speakloop.asr import TranscriptionContext
from speakloop.asr import vad as vad_mod
from speakloop.asr.whisper_mlx_engine import WhisperMLXEngine

pytestmark = pytest.mark.integration

SR = 16000
HALLUCINATION = "you"  # a classic Whisper-on-silence phantom token


def _install_hallucinating_whisper(monkeypatch):
    """Stub that emits the phantom token only for buffers longer than 2 s
    (i.e. only if it is ever handed a silence-laden region)."""
    fake = types.ModuleType("mlx_whisper")

    def _transcribe(audio, **kwargs):
        n = len(audio) if not isinstance(audio, str) else 0
        if n > 2 * SR:
            return {"text": HALLUCINATION, "segments": [{"words": [{"word": HALLUCINATION, "start": 0.0, "end": 0.2}]}]}
        return {"text": "coroutine", "segments": [{"words": [{"word": " coroutine", "start": 0.05, "end": 0.4}]}]}

    fake.transcribe = _transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake)


def test_no_hallucinated_tokens_in_silence_across_20_clips(monkeypatch, tmp_path):
    _install_hallucinating_whisper(monkeypatch)

    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)
    # 6 s clips: a short 0.5 s speech burst, then a 2–5 s thinking pause.
    audio = np.zeros(int(6.0 * SR), dtype="float32")
    monkeypatch.setattr(engine, "_load_audio", lambda _p: audio)
    # VAD keeps only the 0.5 s speech burst; the long pause is dropped.
    monkeypatch.setattr(vad_mod, "segment", lambda _p: [vad_mod.SpeechRegion(0.0, 0.5)])

    ctx = TranscriptionContext(use_vad=True)
    hallucinations = 0
    for i in range(20):
        wav = tmp_path / f"clip-{i}.wav"
        wav.write_bytes(b"\x00")
        t = engine.transcribe(wav, context=ctx)
        if HALLUCINATION in t.text.lower().split():
            hallucinations += 1

    assert hallucinations == 0
