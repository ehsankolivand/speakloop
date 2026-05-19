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
