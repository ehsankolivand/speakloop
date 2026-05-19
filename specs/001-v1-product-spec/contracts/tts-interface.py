"""
TTS module public interface — STABLE contract.

Constitution Principle V (Swappable Engines): only files inside
`src/speakloop/tts/` may import engine-specific packages such as
`kokoro_mlx` or `mlx_audio`. Every other module in the codebase imports
from `speakloop.tts` and depends only on the `TTSEngine` Protocol below.

Swapping Kokoro for Piper or any future engine MUST require changes in
exactly one file (`tts/<engine>_engine.py`) plus, at most, an entry in
`installer/manifest.py`. The Protocol below MUST NOT change shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TTSEngine(Protocol):
    """A text-to-speech engine that can render text to a WAV file."""

    def synthesize(self, text: str, voice: str | None = None) -> Path:
        """
        Render `text` to a WAV file and return its path.

        The implementation MUST honour FR-004 by caching identical
        (voice, text) pairs. Subsequent calls with the same inputs MUST
        return the path to an already-cached WAV without re-synthesising.

        Args:
            text: The exact text to speak. Surrounding whitespace is
                stripped; the engine is responsible for sentence
                splitting if the text exceeds its single-chunk limit.
            voice: Engine-specific voice identifier (e.g. ``"bm_george"``
                for Kokoro British male). ``None`` means "engine default".

        Returns:
            Absolute path to the WAV file on local disk. The caller is
            free to read it; the engine retains ownership and may keep
            it indefinitely as a cache entry.

        Raises:
            TTSEngineError: if synthesis fails for any reason. The
                wrapper layer (`tts/__init__.py`) MUST translate
                engine-specific exceptions into this single class so
                callers do not depend on engine internals.
        """
        ...

    def available_voices(self) -> list[str]:
        """Return the list of voice identifiers this engine supports."""
        ...


class TTSEngineError(Exception):
    """Single public error class for all TTS failures."""
