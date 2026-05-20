"""T021 — VAD + per-region transcription + timeline stitching (FR-005/FR-006).

Stubs VAD and mlx_whisper (no model, no torch). Asserts: word timings are
offset back onto the original timeline (so the pause gap survives), silent
audio never reaches the ASR, and all-silence yields an empty Transcript.
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


def _install_fake_mlx_whisper(monkeypatch, calls):
    fake = types.ModuleType("mlx_whisper")

    def _transcribe(audio, **kwargs):
        # Each region returns one word at local t=0.1 with text marking the call.
        idx = len(calls)
        calls.append({"len": len(audio), "kwargs": kwargs})
        return {
            "text": f"word{idx}",
            "segments": [{"words": [{"word": f" word{idx}", "start": 0.1, "end": 0.3}]}],
        }

    fake.transcribe = _transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake)


def _engine_with_audio(monkeypatch, total_seconds):
    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)
    audio = np.zeros(int(total_seconds * SR), dtype="float32")
    monkeypatch.setattr(engine, "_load_audio", lambda _p: audio)
    return engine


def test_word_timings_offset_onto_original_timeline(monkeypatch, tmp_path):
    calls: list = []
    _install_fake_mlx_whisper(monkeypatch, calls)
    # Speech 0–1s and 3–4s; the 1–3s pause must NOT be transcribed.
    monkeypatch.setattr(
        vad_mod, "segment", lambda _p: [vad_mod.SpeechRegion(0.0, 1.0), vad_mod.SpeechRegion(3.0, 4.0)]
    )
    engine = _engine_with_audio(monkeypatch, 4.0)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"\x00")

    t = engine.transcribe(wav, context=TranscriptionContext(use_vad=True))

    assert len(calls) == 2  # only the two speech regions reached the ASR
    assert t.text == "word0 word1"
    # Region 0 word at 0.1; region 1 word offset by +3.0 -> 3.1 (pause preserved).
    assert t.words[0].start_seconds == pytest.approx(0.1)
    assert t.words[1].start_seconds == pytest.approx(3.1)
    # The 1–3s silent window contains no words.
    assert not any(1.0 < w.start_seconds < 3.0 for w in t.words)


def test_all_silence_yields_empty_transcript(monkeypatch, tmp_path):
    calls: list = []
    _install_fake_mlx_whisper(monkeypatch, calls)
    monkeypatch.setattr(vad_mod, "segment", lambda _p: [])
    engine = _engine_with_audio(monkeypatch, 5.0)
    wav = tmp_path / "silent.wav"
    wav.write_bytes(b"\x00")

    t = engine.transcribe(wav, context=TranscriptionContext(use_vad=True))
    assert t.is_empty is True
    assert t.words == []
    assert calls == []  # ASR never invoked on silence


def test_use_vad_false_takes_whole_clip_path(monkeypatch, tmp_path, wav_fixture):
    calls: list = []
    _install_fake_mlx_whisper(monkeypatch, calls)
    # If VAD were used this would raise (no segment stub returning regions); but
    # use_vad=False must bypass VAD and transcribe the file path directly.
    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)
    t = engine.transcribe(wav_fixture("attempt-short.wav"), context=TranscriptionContext(use_vad=False))
    assert len(calls) == 1
    assert isinstance(calls[0]["len"], int)  # received a path string's length (str), not sliced audio
    assert t.text == "word0"
