"""
ASR module public interface — STABLE contract.

Constitution Principle V: only files inside `src/speakloop/asr/` may
import engine-specific packages such as `parakeet_mlx`. Every other
module imports from `speakloop.asr` and depends only on the `ASREngine`
Protocol below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    words: list[WordTiming] = field(default_factory=list)
    audio_duration_seconds: float = 0.0

    @property
    def is_empty(self) -> bool:
        """True if the user produced no measurable speech."""
        return self.text.strip() == ""


class ASREngine(Protocol):
    """A speech-to-text engine that transcribes a WAV file."""

    def transcribe(self, wav_path: Path) -> Transcript: ...


class ASREngineError(Exception):
    """Single public error class for all ASR failures."""
