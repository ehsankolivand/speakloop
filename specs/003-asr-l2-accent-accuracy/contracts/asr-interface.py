"""Contract: the ASR public surface after 003-asr-l2-accent-accuracy.

This is the STABLE contract the rest of speakloop depends on. It extends the v1
`asr/interface.py` additively: `Transcript`/`WordTiming` are unchanged, and
`ASREngine.transcribe` gains one optional keyword `context`. Engine-specific
packages (`mlx_whisper`, `parakeet_mlx`, `silero_vad`, `onnxruntime`) are imported
ONLY inside `asr/` wrapper/helper files (Constitution Principle V).

Implementations:
  - WhisperMLXEngine  (asr/whisper_mlx_engine.py)  — DEFAULT; consumes `context`
  - ParakeetEngine    (asr/parakeet_engine.py)     — fallback; accepts+ignores `context`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


# --- Unchanged from v1 -------------------------------------------------------

@dataclass(frozen=True)
class WordTiming:
    word: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class Transcript:
    text: str
    words: list[WordTiming] = field(default_factory=list)
    audio_duration_seconds: float = 0.0

    @property
    def is_empty(self) -> bool:
        return self.text.strip() == ""


# --- New (additive) ----------------------------------------------------------

@dataclass(frozen=True)
class TranscriptionContext:
    """Per-session biasing payload. Optional; None means 'no biasing, VAD default'.

    `initial_prompt` is the assembled domain prompt (accent declaration + mined
    question terms + seed lexicon). `initial_prompt_sha256` is the hex digest of
    that exact string ("" when prompt is None) and is recorded in provenance for
    reproducibility (FR-007). `use_vad` toggles Silero pre-segmentation in the
    Whisper path (default on; Parakeet ignores it).
    """

    initial_prompt: str | None = None
    initial_prompt_sha256: str = ""
    use_vad: bool = True


class ASREngine(Protocol):
    """A speech-to-text engine that transcribes a WAV file.

    The `context` keyword is OPTIONAL and additive: existing callers that pass
    nothing keep working unchanged. Engines that cannot use context (Parakeet)
    accept and ignore it.
    """

    def transcribe(
        self,
        wav_path: Path,
        *,
        context: "TranscriptionContext | None" = None,
    ) -> Transcript: ...

    def ensure_loaded(self) -> None:
        """Eagerly load the model (so selection can detect load failure before
        attempt 1). Idempotent; safe to call repeatedly. Raises ASREngineError
        on failure."""
        ...


class ASREngineError(Exception):
    """Single public error class for all ASR failures (unchanged)."""


# --- Engine selection + fallback (asr/selection.py) --------------------------

@dataclass(frozen=True)
class EngineSelection:
    """Outcome of resolving which engine actually runs (FR-002, FR-009, SC-F)."""

    engine: ASREngine
    engine_name: str          # "whisper" | "parakeet"
    model_id: str
    fell_back: bool
    fallback_reason: str | None = None


def build_engine(name: str | None = None) -> EngineSelection:
    """Construct + eagerly load the requested engine (default: whisper).

    On load failure of the requested engine, fall back to Parakeet, set
    fell_back=True and an English fallback_reason. An explicit name="parakeet"
    is honored with no fallback. The returned engine is resident and reused
    across attempts/sessions/replays with no reload (research §c).

    Principle V: this function imports the two wrapper CLASSES (both inside
    `asr/`) but no third-party engine package itself.
    """
    ...
