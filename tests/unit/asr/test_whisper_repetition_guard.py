"""Unit test for the Whisper repetition-loop guard (anti-hallucination flags).

A low-confidence Whisper decode can repeat one token hundreds of times
("Come Come Come…" observed on a 15.8 s live attempt). The engine forwards the
documented decoding flags (temperature fallback + compression-ratio / logprob /
no-speech thresholds) and, as a post-hoc safety net, drops a decode whose gzip
compression ratio is degenerate, logging a warning.
"""

from __future__ import annotations

import logging
import sys
import types

import numpy as np
import pytest

from speakloop.asr import TranscriptionContext
from speakloop.asr import vad as vad_mod
from speakloop.asr.whisper_mlx_engine import WhisperMLXEngine

pytestmark = pytest.mark.unit

SR = 16000
_REPEAT = "Come " * 250  # 250+ repetitions → very high compression ratio


def _install_repeating_whisper(monkeypatch, captured):
    fake = types.ModuleType("mlx_whisper")

    def _transcribe(audio, **kwargs):
        captured.update(kwargs)
        return {
            "text": _REPEAT,
            "segments": [
                {"words": [{"word": " Come", "start": float(i) * 0.05, "end": float(i) * 0.05 + 0.04}
                           for i in range(250)]}
            ],
        }

    fake.transcribe = _transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake)


def test_decode_guards_are_forwarded(monkeypatch, wav_fixture):
    captured: dict = {}
    _install_repeating_whisper(monkeypatch, captured)
    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)

    engine.transcribe(wav_fixture("attempt-short.wav"), context=TranscriptionContext(use_vad=False))

    # The documented anti-hallucination flags reach mlx_whisper.transcribe.
    assert captured["temperature"] == (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    assert captured["compression_ratio_threshold"] == 2.4
    assert captured["logprob_threshold"] == -1.0
    assert captured["no_speech_threshold"] == 0.6


def test_whole_clip_repetition_loop_is_dropped_with_warning(monkeypatch, wav_fixture, caplog):
    _install_repeating_whisper(monkeypatch, {})
    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)

    with caplog.at_level(logging.WARNING):
        t = engine.transcribe(
            wav_fixture("attempt-short.wav"), context=TranscriptionContext(use_vad=False)
        )

    assert t.is_empty is True
    assert t.words == []
    assert any("degenerate repetition" in r.message for r in caplog.records)


def test_vad_region_repetition_loop_is_dropped_with_warning(monkeypatch, tmp_path, caplog):
    _install_repeating_whisper(monkeypatch, {})
    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)
    monkeypatch.setattr(engine, "_load_audio", lambda _p: np.zeros(int(2.0 * SR), dtype="float32"))
    monkeypatch.setattr(vad_mod, "segment", lambda _p: [vad_mod.SpeechRegion(0.0, 2.0)])

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"\x00")
    with caplog.at_level(logging.WARNING):
        t = engine.transcribe(wav, context=TranscriptionContext(use_vad=True))

    # The degenerate region is dropped → no text, no words; the rest of the
    # transcript (here, nothing else) is unaffected.
    assert t.text == ""
    assert t.words == []
    assert any("degenerate repetition" in r.message for r in caplog.records)


def test_normal_transcript_is_not_dropped(monkeypatch, wav_fixture):
    fake = types.ModuleType("mlx_whisper")
    fake.transcribe = lambda audio, **kw: {
        "text": "coroutines run on a shared pool of threads and suspend cooperatively",
        "segments": [{"words": [{"word": " coroutines", "start": 0.0, "end": 0.5}]}],
    }
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake)
    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)

    t = engine.transcribe(wav_fixture("attempt-short.wav"), context=TranscriptionContext(use_vad=False))
    assert "coroutines" in t.text
    assert not t.is_empty
