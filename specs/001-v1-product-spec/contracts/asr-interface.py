"""
ASR module public interface — STABLE contract.

Constitution Principle V (Swappable Engines): only files inside
`src/speakloop/asr/` may import engine-specific packages such as
`parakeet_mlx`, `mlx_whisper`, or `faster_whisper`. Every other module
imports from `speakloop.asr` and depends only on the `ASREngine`
Protocol below.

Swapping Parakeet for any future engine MUST require changes in exactly
one file (`asr/<engine>_engine.py`) plus, at most, an entry in
`installer/manifest.py`. The Protocol below MUST NOT change shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class WordTiming:
    """A single word with its start/end times in seconds."""

    word: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class Transcript:
    """Result of one ASR pass over a single audio file."""

    text: str
    words: list[WordTiming]
    audio_duration_seconds: float

    @property
    def is_empty(self) -> bool:
        """True if the user produced no measurable speech."""
        return self.text.strip() == ""


class ASREngine(Protocol):
    """A speech-to-text engine that transcribes a WAV file to text plus word timings."""

    def transcribe(self, wav_path: Path) -> Transcript:
        """
        Transcribe the WAV file at `wav_path`.

        Implementations MUST return word-level timings so the metrics
        module can compute pause distributions without re-running VAD on
        the raw audio.

        Args:
            wav_path: Local path to a single mono WAV file (any sample
                rate the engine supports — Parakeet prefers 16 kHz).

        Returns:
            A `Transcript`. If the user stayed silent, `transcript.text`
            is the empty string and `transcript.words` is `[]`; callers
            MUST handle this case (the report acknowledges silent
            attempts per spec edge case "User stays silent through an
            attempt").

        Raises:
            ASREngineError: if transcription fails for any reason.
        """
        ...


class ASREngineError(Exception):
    """Single public error class for all ASR failures."""
