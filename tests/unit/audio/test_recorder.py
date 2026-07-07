"""T051 — recorder writes a WAV; early-exit cuts it short."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest
import soundfile as sf

from speakloop.audio import recorder

pytestmark = pytest.mark.unit


class FakeInputStream:
    def __init__(self, samplerate, channels, dtype, callback):
        self._sr = samplerate
        self._ch = channels
        self._callback = callback
        self._thread = None
        self._stop = threading.Event()

    def __enter__(self):
        def loop():
            n_per_chunk = max(1, int(self._sr * 0.05))
            while not self._stop.is_set():
                self._callback(
                    np.zeros((n_per_chunk, self._ch), dtype=np.float32),
                    n_per_chunk,
                    None,
                    None,
                )
                time.sleep(0.05)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


def test_record_writes_wav(monkeypatch, tmp_path):
    monkeypatch.setattr("sounddevice.InputStream", FakeInputStream)
    out = tmp_path / "out.wav"
    duration = recorder.record(out, time_budget_seconds=0.5)
    assert out.exists()
    assert duration >= 0.4
    data, sr = sf.read(str(out))
    assert sr == recorder.DEFAULT_SAMPLE_RATE
    assert len(data) > 0


class _OverflowStatus:
    input_overflow = True  # sounddevice.CallbackFlags-like: a dropped-samples signal


class OverflowInputStream(FakeInputStream):
    """Like FakeInputStream but delivers each chunk with an input-overflow status."""

    def __enter__(self):
        def loop():
            n = max(1, int(self._sr * 0.05))
            while not self._stop.is_set():
                self._callback(np.zeros((n, self._ch), dtype=np.float32), n, None, _OverflowStatus())
                time.sleep(0.05)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self


def test_record_warns_on_input_overflow(monkeypatch, tmp_path, caplog):
    """IMP-029: dropped mic samples (input overflow) are surfaced as one warning, not
    silently discarded."""
    monkeypatch.setattr("sounddevice.InputStream", OverflowInputStream)
    out = tmp_path / "out.wav"
    with caplog.at_level("WARNING", logger="speakloop.audio.recorder"):
        recorder.record(out, time_budget_seconds=0.3)
    assert any("input overflow" in r.message.lower() for r in caplog.records)
    assert out.exists()  # still writes the (degraded) recording


def test_record_no_overflow_warning_on_clean_capture(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr("sounddevice.InputStream", FakeInputStream)  # status=None
    with caplog.at_level("WARNING", logger="speakloop.audio.recorder"):
        recorder.record(tmp_path / "out.wav", time_budget_seconds=0.3)
    assert not any("overflow" in r.message.lower() for r in caplog.records)


def test_record_respects_early_exit(monkeypatch, tmp_path):
    monkeypatch.setattr("sounddevice.InputStream", FakeInputStream)
    out = tmp_path / "out.wav"
    event = threading.Event()

    def stop_soon():
        time.sleep(0.2)
        event.set()

    t = threading.Thread(target=stop_soon, daemon=True)
    t.start()
    duration = recorder.record(out, time_budget_seconds=5.0, early_exit_event=event)
    assert duration < 1.0  # exited before the 5s budget
    t.join(timeout=1.0)
