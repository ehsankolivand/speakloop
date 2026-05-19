"""Microphone recorder using sounddevice.InputStream + soundfile.

The early_exit_event lets the coordinator stop recording before the time
budget elapses (FR-007).
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

DEFAULT_SAMPLE_RATE = 16000


class RecorderError(RuntimeError):
    pass


def record(
    out_path: Path,
    time_budget_seconds: float,
    early_exit_event: threading.Event | None = None,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = 1,
) -> float:
    """Record audio to `out_path` for up to `time_budget_seconds`.

    Returns the actual wall-clock duration recorded.
    Stops early when `early_exit_event` is set.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    early_exit_event = early_exit_event or threading.Event()

    # Lazy import: audio → sessions creates a module-load cycle through
    # sessions/__init__.py → coordinator → audio.recorder.
    from speakloop.sessions import abort

    chunks: queue.Queue[np.ndarray] = queue.Queue()

    def _callback(indata, frames, time_info, status):
        if status:
            # don't raise inside the audio thread — surface later if needed
            pass
        chunks.put(indata.copy())

    start = time.monotonic()
    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            callback=_callback,
        ):
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= time_budget_seconds:
                    break
                if early_exit_event.is_set():
                    break
                if abort.abort_event.is_set():
                    # SIGINT — leave the loop within one sleep tick (~50 ms)
                    # instead of waiting out the full time budget (FR-016).
                    break
                # short sleep so the early-exit and time-budget checks remain responsive
                time.sleep(0.05)
    except sd.PortAudioError as e:
        raise RecorderError(f"Recording failed: {e}. Run `speakloop doctor` to diagnose.") from e

    duration = time.monotonic() - start

    # Drain queue into an array.
    pieces = []
    while not chunks.empty():
        pieces.append(chunks.get_nowait())
    if pieces:
        audio = np.concatenate(pieces, axis=0)
    else:
        audio = np.zeros((0, channels), dtype=np.float32)

    sf.write(out_path, audio, sample_rate)
    return duration
