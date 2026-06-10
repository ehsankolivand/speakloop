"""Audio playback via sounddevice + soundfile."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


class PlaybackError(RuntimeError):
    """Raised when no output device is available."""


# 012: how often the interruptible-playback loop checks the stop predicate. Measured
# `sd.stop()` latency ≈ 110 ms, so a 30 ms poll keeps the worst-case skip well under the
# 500 ms target (SC-004).
_POLL_INTERVAL_SECONDS = 0.03


# macOS CoreAudio fails to open an output stream when the device PortAudio has
# cached is no longer valid. The most common trigger is the output device going
# away mid-session — e.g. Bluetooth headphones powered off: macOS moves the
# system default to the built-in speakers, but PortAudio still holds the device
# table it read at import time, so it tries to open the dead device and reports
# `paInternalError` (-9986) preceded by AUHAL "!obj" (null device object)
# warnings and `kAudioUnitErr_InvalidPropertyValue` (-10851). The same symptom
# also appears on a cold first open or when the idle 48 kHz speakers are asked to
# switch to the clip's 24 kHz rate. So before giving up we (a) reload PortAudio
# to re-read the device table and pick up the new default, retrying the open, and
# (b) resample to the device's native rate so the hardware rate never changes.
_OPEN_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 0.25


def _reinitialize() -> None:
    """Reload PortAudio so a changed device list (e.g. headphones powered off) is
    re-read and the current system-default output is used on the next open."""
    try:
        sd._terminate()
        sd._initialize()
    except Exception:
        pass


def _play_blocking(data, samplerate: int) -> None:
    sd.play(data, samplerate=samplerate)
    sd.wait()


def _device_output_rate() -> int:
    """The default output device's native sample rate, or 0 if unavailable."""
    try:
        return int(sd.query_devices(kind="output")["default_samplerate"])
    except Exception:
        return 0


def _resample(data, src_rate: int, dst_rate: int):
    """Resample float32 audio (1-D mono or 2-D frames×channels) to dst_rate."""
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(int(src_rate), int(dst_rate))
    up, down = int(dst_rate) // g, int(src_rate) // g
    out = resample_poly(data, up, down, axis=0)
    return out.astype("float32").clip(-1.0, 1.0)


def play(wav_path: Path) -> None:
    """Play a WAV file synchronously, blocking until playback finishes.

    Resilient to a mid-session output-device change (the common case: Bluetooth
    headphones powered off): on a PortAudio failure the device table is reloaded
    and the open retried, and if it still fails the clip is resampled to the
    default output device's native rate (so PortAudio never has to switch the
    hardware sample rate — the usual `-10851` trigger) before a final attempt.
    """
    if not Path(wav_path).exists():
        raise PlaybackError(f"WAV not found: {wav_path}")
    try:
        data, sample_rate = sf.read(str(wav_path), dtype="float32")
    except (FileNotFoundError, sf.LibsndfileError) as e:
        raise PlaybackError(f"Could not read WAV: {wav_path}: {e}") from e

    last_err: Exception | None = None

    # 1) Play at the clip's own rate. On failure, reload PortAudio so a device
    #    that vanished mid-session is dropped and the new default is used, then
    #    retry the open.
    for attempt in range(_OPEN_RETRIES):
        try:
            _play_blocking(data, sample_rate)
            return
        except sd.PortAudioError as e:
            last_err = e
            sd.stop(ignore_errors=True)
            if attempt < _OPEN_RETRIES - 1:
                _reinitialize()
                time.sleep(_RETRY_BACKOFF_SECONDS)

    # 2) Fallback: resample to the device's native rate so the hardware rate
    #    never has to change. Best-effort — any failure keeps the original error.
    device_rate = _device_output_rate()
    if device_rate and device_rate != int(sample_rate):
        try:
            _play_blocking(_resample(data, int(sample_rate), device_rate), device_rate)
            return
        except Exception as e:  # PortAudio failure, or SciPy unavailable
            last_err = e
            sd.stop(ignore_errors=True)

    raise PlaybackError(
        f"Audio output failed: {last_err}. Run `speakloop doctor` to diagnose."
    ) from last_err


def warm_output_device() -> None:
    """Pay the one-time CoreAudio output-device open up front (012, FR-023 sibling).

    A tiny silent play absorbs the device-open latency (measured ~0.2–1.9 s on a cold
    process) so the first real clip is not delayed. Best-effort — any failure is
    swallowed (the first real `play`/`play_interruptible` will surface a genuine error)."""
    try:
        sd.play(np.zeros((1200, 1), dtype="float32"), samplerate=24000)
        sd.wait()
    except Exception:  # noqa: BLE001 — warm-up is best-effort; never block the session
        sd.stop(ignore_errors=True)


def _start_nonblocking(data, sample_rate: int) -> int:
    """Start a non-blocking `sd.play`, reusing `play`'s device-loss/resample recovery.

    Returns the effective samplerate the stream was started at; raises `PlaybackError`
    if the device cannot be opened. Mirrors `play` step-for-step but does NOT `sd.wait`."""
    last_err: Exception | None = None
    for attempt in range(_OPEN_RETRIES):
        try:
            sd.play(data, samplerate=sample_rate)
            return int(sample_rate)
        except sd.PortAudioError as e:
            last_err = e
            sd.stop(ignore_errors=True)
            if attempt < _OPEN_RETRIES - 1:
                _reinitialize()
                time.sleep(_RETRY_BACKOFF_SECONDS)
    device_rate = _device_output_rate()
    if device_rate and device_rate != int(sample_rate):
        try:
            sd.play(_resample(data, int(sample_rate), device_rate), samplerate=device_rate)
            return int(device_rate)
        except Exception as e:  # PortAudio failure, or SciPy unavailable
            last_err = e
            sd.stop(ignore_errors=True)
    raise PlaybackError(
        f"Audio output failed: {last_err}. Run `speakloop doctor` to diagnose."
    ) from last_err


def play_interruptible(
    wav_path: Path,
    *,
    should_stop: Callable[[], bool],
    on_first_frame: Callable[[], None] | None = None,
    poll_interval: float = _POLL_INTERVAL_SECONDS,
) -> bool:
    """Play a WAV non-blocking, stopping early when ``should_stop()`` returns True.

    Returns ``True`` if playback was interrupted, ``False`` if it ran to completion.
    Used by the listen loop so a single keypress skips a clip within ~110 ms (SC-004).
    Reuses ``play``'s resilience to a mid-session output-device change."""
    if not Path(wav_path).exists():
        raise PlaybackError(f"WAV not found: {wav_path}")
    try:
        data, sample_rate = sf.read(str(wav_path), dtype="float32")
    except (FileNotFoundError, sf.LibsndfileError) as e:
        raise PlaybackError(f"Could not read WAV: {wav_path}: {e}") from e

    _start_nonblocking(data, int(sample_rate))
    if on_first_frame is not None:
        on_first_frame()

    interrupted = False
    try:
        while True:
            stream = sd.get_stream()
            if stream is None or not stream.active:
                break  # playback finished on its own
            if should_stop():
                interrupted = True
                break
            time.sleep(poll_interval)
    finally:
        if interrupted:
            sd.stop(ignore_errors=True)
        else:
            # Ensure the buffer fully drained before returning (no clipped tail).
            try:
                sd.wait()
            except Exception:  # noqa: BLE001 — best-effort drain
                sd.stop(ignore_errors=True)
    return interrupted
