"""Audio playback via sounddevice + soundfile."""

from __future__ import annotations

from pathlib import Path

import sounddevice as sd
import soundfile as sf


class PlaybackError(RuntimeError):
    """Raised when no output device is available."""


def play(wav_path: Path) -> None:
    """Play a WAV file synchronously, blocking until playback finishes."""
    if not Path(wav_path).exists():
        raise PlaybackError(f"WAV not found: {wav_path}")
    try:
        data, sample_rate = sf.read(str(wav_path), dtype="float32")
    except (FileNotFoundError, sf.LibsndfileError) as e:
        raise PlaybackError(f"Could not read WAV: {wav_path}: {e}") from e

    try:
        sd.play(data, samplerate=sample_rate)
        sd.wait()
    except sd.PortAudioError as e:
        raise PlaybackError(f"Audio output failed: {e}. Run `speakloop doctor` to diagnose.") from e
