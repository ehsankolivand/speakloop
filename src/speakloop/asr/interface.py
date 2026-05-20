"""
ASR module public interface — STABLE contract.

Constitution Principle V: only files inside `src/speakloop/asr/` may
import engine-specific packages such as `parakeet_mlx`, `mlx_whisper`,
`silero_vad`, or `onnxruntime`. Every other module imports from
`speakloop.asr` and depends only on the `ASREngine` Protocol below.

003-asr-l2-accent-accuracy additively extended this contract:
`transcribe` gained an optional `context` keyword and the Protocol gained
`ensure_loaded`. `Transcript`/`WordTiming`/`ASREngineError` are unchanged,
so every v1 caller keeps working without modification.
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


@dataclass(frozen=True)
class TranscriptionContext:
    """Per-session biasing payload passed into :meth:`ASREngine.transcribe`.

    Additive (003-asr-l2-accent-accuracy, data-model §A.1). ``None`` means "no
    biasing, VAD at its default". ``initial_prompt`` is the assembled domain
    prompt (accent declaration + question-mined terms + seed lexicon);
    ``initial_prompt_sha256`` is the hex digest of that exact string (``""`` when
    the prompt is ``None``) and is recorded in report provenance for
    reproducibility (FR-007). ``use_vad`` toggles Silero pre-segmentation in the
    Whisper path (default on; engines that can't use it ignore it).
    """

    initial_prompt: str | None = None
    initial_prompt_sha256: str = ""
    use_vad: bool = True


class ASREngine(Protocol):
    """A speech-to-text engine that transcribes a WAV file.

    The ``context`` keyword is OPTIONAL and additive: callers that pass nothing
    keep working unchanged, and engines that cannot use context accept and
    ignore it.
    """

    def transcribe(
        self,
        wav_path: Path,
        *,
        context: TranscriptionContext | None = None,
    ) -> Transcript: ...

    def ensure_loaded(self) -> None:
        """Eagerly load the model so a load failure surfaces before attempt 1
        (used by engine selection). Idempotent; raises ASREngineError on
        failure."""
        ...


class ASREngineError(Exception):
    """Single public error class for all ASR failures."""
