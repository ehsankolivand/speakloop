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
# Kokoro's native playback-speed multiplier. 1.0 = engine default; values
# below 1.0 slow the speech down (helpful for shadowing / focused listening).
DEFAULT_SPEED = 1.0


class KokoroEngine:
    """Kokoro-82M synthesizer with content-addressed disk caching (FR-004).

    ``speed`` is Kokoro's native multiplier (1.0 = default cadence; < 1.0 =
    slower). It is fixed per engine instance and folded into the clip cache key
    so clips at different speeds never collide.
    """

    def __init__(
        self, default_voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED
    ) -> None:
        self._default_voice = default_voice
        self._speed = speed
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

    def synthesize(
        self, text: str, voice: str | None = None, speed: float | None = None
    ) -> Path:
        """Render ``text`` to a cached WAV.

        ``speed`` is an OPTIONAL per-call override of the instance default (``self._speed``).
        Kokoro's ``save`` accepts a per-call speed natively, and the clip cache already keys
        on speed, so a single engine instance can render the same text at several speeds
        (e.g. the normal drill cadence and the slower focused teaching beat) without a second
        model load and without clips at different speeds colliding. ``None`` ⇒ instance speed.
        This is a backward-compatible superset of the ``TTSEngine`` Protocol (which other
        modules call as ``synthesize(text)`` / ``synthesize(text, voice)``)."""
        text = (text or "").strip()
        if not text:
            raise TTSEngineError("Cannot synthesize empty text.")
        voice = voice or self._default_voice
        eff_speed = self._speed if speed is None else float(speed)

        cached = cache.lookup(voice, text, eff_speed)
        if cached is not None:
            return cached

        tts = self._load()
        # Write directly to the cache target using KokoroTTS.save (which
        # internally generates + writes a WAV file).
        cache_dir = paths.ensure_dir(paths.tts_cache_dir())
        scratch = cache_dir / f".tmp-{cache.cache_key(voice, text, eff_speed)}.wav"
        try:
            tts.save(text, str(scratch), voice=voice, speed=eff_speed)
        except Exception as e:  # pragma: no cover — engine-specific failures
            if scratch.exists():
                scratch.unlink()
            raise TTSEngineError(f"Kokoro synthesis failed: {e}") from e

        try:
            stored = cache.store(voice, text, scratch, eff_speed)
        finally:
            if scratch.exists():
                scratch.unlink()
        # 012: keep the content-addressed cache under its size cap; never evict the clip
        # we just stored (it is about to be played).
        cache.prune(keep=stored)
        return stored

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
