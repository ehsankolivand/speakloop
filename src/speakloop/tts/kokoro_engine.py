"""Kokoro-82M TTS wrapper.

This is the ONLY file in the repo allowed to import `kokoro_mlx` or
`mlx_audio` (Constitution Principle V, audited by T109).

Real API (verified via `inspect.signature` against installed `kokoro_mlx`):

    KokoroTTS.from_pretrained(model_id_or_path) -> KokoroTTS
    KokoroTTS.generate(text, voice='af_heart', speed=1.0,
                       sample_rate=24000, language=None) -> TTSResult
    KokoroTTS.save(text, path, voice=..., ...) -> TTSResult
    KokoroTTS.list_voices() -> list[str]
    kokoro_mlx.DEFAULT_VOICE  # 'af_heart'
"""

from __future__ import annotations

from pathlib import Path

from speakloop.config import paths
from speakloop.installer import manifest
from speakloop.tts import cache
from speakloop.tts.interface import TTSEngineError

# Engine's own default — used when the caller passes voice=None.
DEFAULT_VOICE = "af_heart"


class KokoroEngine:
    """Kokoro-82M synthesizer with content-addressed disk caching (FR-004)."""

    def __init__(self, default_voice: str = DEFAULT_VOICE) -> None:
        self._default_voice = default_voice
        self._tts = None  # lazy KokoroTTS instance

    def _load(self):
        """Lazily construct the underlying KokoroTTS instance."""
        if self._tts is not None:
            return self._tts
        try:
            import kokoro_mlx
        except ImportError as e:  # pragma: no cover
            raise TTSEngineError(
                "kokoro_mlx is not installed. Install the Phase-A model bundle: "
                "see specs/001-v1-product-spec/quickstart.md."
            ) from e

        model_path = manifest.KOKORO_82M.local_path
        if not model_path.exists():
            raise TTSEngineError(
                f"Kokoro model not found at {model_path}. "
                "Run `speakloop practice` to consent and download it."
            )

        try:
            self._tts = kokoro_mlx.KokoroTTS.from_pretrained(str(model_path))
        except Exception as e:  # pragma: no cover — engine-specific failures
            raise TTSEngineError(f"Kokoro load failed from {model_path}: {e}") from e
        return self._tts

    def synthesize(self, text: str, voice: str | None = None) -> Path:
        text = (text or "").strip()
        if not text:
            raise TTSEngineError("Cannot synthesize empty text.")
        voice = voice or self._default_voice

        cached = cache.lookup(voice, text)
        if cached is not None:
            return cached

        tts = self._load()
        # Write directly to the cache target using KokoroTTS.save (which
        # internally generates + writes a WAV file).
        cache_dir = paths.ensure_dir(paths.tts_cache_dir())
        scratch = cache_dir / f".tmp-{cache.cache_key(voice, text)}.wav"
        try:
            tts.save(text, str(scratch), voice=voice)
        except Exception as e:  # pragma: no cover — engine-specific failures
            if scratch.exists():
                scratch.unlink()
            raise TTSEngineError(f"Kokoro synthesis failed: {e}") from e

        try:
            return cache.store(voice, text, scratch)
        finally:
            if scratch.exists():
                scratch.unlink()

    def available_voices(self) -> list[str]:
        # Querying the live engine costs a model load; return the engine's
        # published voice catalog directly. The engine itself accepts any
        # voice; this list is informational.
        try:
            return self._load().list_voices()
        except TTSEngineError:
            # Fallback to a documented subset if the engine isn't loadable
            # (e.g., model not yet downloaded).
            return [
                DEFAULT_VOICE,
                "af_bella",
                "af_sarah",
                "am_michael",
                "am_adam",
                "bm_george",
                "bm_lewis",
            ]
