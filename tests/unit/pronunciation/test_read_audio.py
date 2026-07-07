"""IMP-022 — Wav2Vec2Scorer._read_audio silence/length/averaging/resample gating (no model).

`_read_audio` is a pure staticmethod that decides the user-facing `not_captured` outcome via
model-free rules: multi-channel averaging (`mean(axis=1)`), a min-length gate, an RMS silence
gate, and a scipy resample to 16 kHz. Every other `not_captured` test fakes a scorer that just
returns the status, so the actual gating math was never exercised. These pin it — a regression
in either threshold, the RMS formula, or the resample path would drop real speech or score
silence.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from speakloop.pronunciation.wav2vec2_engine import _SAMPLE_RATE, Wav2Vec2Scorer

pytestmark = pytest.mark.unit

_RECORDINGS = Path(__file__).parents[2] / "fixtures" / "wav" / "recordings"


def _write(tmp_path, data, sr) -> Path:
    p = tmp_path / "clip.wav"
    sf.write(str(p), data, sr)
    return p


def test_silent_clip_is_gated_by_rms():
    # The committed silent fixture (3 s of zeros @ 22050) → resampled to 16 kHz, still silent →
    # the RMS gate returns None (the user-facing `not_captured` outcome). Also proves the clip
    # is long enough to reach the RMS gate (so it's the RMS branch, not the length branch).
    assert Wav2Vec2Scorer._read_audio(_RECORDINGS / "attempt-silent.wav") is None


def test_normal_clip_returns_16k_float32_mono_array():
    # A real loud clip (~4.5 s @ 22050) passes both gates and comes back resampled to 16 kHz.
    out = Wav2Vec2Scorer._read_audio(_RECORDINGS / "attempt-3s.wav")
    assert out is not None
    assert out.dtype == np.float32
    assert out.ndim == 1


def test_too_short_clip_is_gated_by_length(tmp_path):
    # < _MIN_SPEECH_SECONDS worth of samples, but LOUD — so only the length gate can fire.
    loud_short = (0.3 * np.ones(1000, dtype="float32"))  # 1000 samples @ 16 kHz = 0.0625 s
    assert Wav2Vec2Scorer._read_audio(_write(tmp_path, loud_short, _SAMPLE_RATE)) is None


def test_two_channel_clip_is_averaged_to_mono(tmp_path):
    rng = np.random.default_rng(0)
    stereo = (0.3 * rng.standard_normal((_SAMPLE_RATE, 2))).astype("float32")  # 1 s, loud
    out = Wav2Vec2Scorer._read_audio(_write(tmp_path, stereo, _SAMPLE_RATE))
    assert out is not None
    assert out.ndim == 1  # averaged down to mono
    assert out.shape[0] == _SAMPLE_RATE  # one channel's worth of samples, unresampled


def test_off_rate_clip_is_resampled_to_16k(tmp_path):
    src_rate = 8000
    loud = (0.3 * np.ones(src_rate, dtype="float32"))  # 1 s @ 8 kHz, loud
    out = Wav2Vec2Scorer._read_audio(_write(tmp_path, loud, src_rate))
    assert out is not None
    assert out.dtype == np.float32
    assert abs(out.shape[0] - _SAMPLE_RATE) <= 1  # 1 s @ 8 kHz → ~16000 samples @ 16 kHz
