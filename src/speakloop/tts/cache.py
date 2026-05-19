"""Content-addressed TTS clip cache. sha256(voice|text) → ~/.speakloop/cache/tts/<key>.wav."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from speakloop.config import paths


def cache_key(voice: str | None, text: str) -> str:
    """Stable cache key derived from sha256(voice|text)."""
    payload = f"{voice or ''}|{text}".encode()
    return hashlib.sha256(payload).hexdigest()


def cache_path(voice: str | None, text: str) -> Path:
    """Return the on-disk path where the WAV for (voice, text) would live."""
    return paths.tts_cache_dir() / f"{cache_key(voice, text)}.wav"


def lookup(voice: str | None, text: str) -> Path | None:
    """Return the cached WAV path if present, else None."""
    p = cache_path(voice, text)
    return p if p.exists() else None


def store(voice: str | None, text: str, source_wav: Path) -> Path:
    """Copy a freshly synthesized WAV into the cache and return the cached path."""
    paths.ensure_dir(paths.tts_cache_dir())
    target = cache_path(voice, text)
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
