"""Content-addressed TTS clip cache. sha256(voice|text) → ~/.speakloop/cache/tts/<key>.wav."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from speakloop.config import paths


def cache_key(voice: str | None, text: str, speed: float = 1.0) -> str:
    """Stable cache key derived from sha256(voice|[speed|]text).

    The playback speed is folded into the key ONLY when it differs from the
    engine default (1.0), so existing default-speed cache entries — and the
    historical key formula — stay byte-for-byte stable.
    """
    speed_tag = "" if speed == 1.0 else f"{speed:g}|"
    payload = f"{voice or ''}|{speed_tag}{text}".encode()
    return hashlib.sha256(payload).hexdigest()


def cache_path(voice: str | None, text: str, speed: float = 1.0) -> Path:
    """Return the on-disk path where the WAV for (voice, text, speed) would live."""
    return paths.tts_cache_dir() / f"{cache_key(voice, text, speed)}.wav"


def lookup(voice: str | None, text: str, speed: float = 1.0) -> Path | None:
    """Return the cached WAV path if present, else None."""
    p = cache_path(voice, text, speed)
    return p if p.exists() else None


def store(voice: str | None, text: str, source_wav: Path, speed: float = 1.0) -> Path:
    """Copy a freshly synthesized WAV into the cache and return the cached path."""
    paths.ensure_dir(paths.tts_cache_dir())
    target = cache_path(voice, text, speed)
    if source_wav.resolve() == target.resolve():
        return target
    shutil.copyfile(source_wav, target)
    return target


def purge() -> int:
    """Delete every cached WAV. Returns the count of removed files."""
    cache_dir = paths.tts_cache_dir()
    if not cache_dir.exists():
        return 0
    n = 0
    for f in cache_dir.iterdir():
        if f.is_file():
            f.unlink()
            n += 1
    return n
