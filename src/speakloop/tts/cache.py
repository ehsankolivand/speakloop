"""Content-addressed TTS clip cache. sha256(voice|text) → ~/.speakloop/cache/tts/<key>.wav."""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
from pathlib import Path

from speakloop.config import paths

# Default size cap for the clip cache (012). The cache is content-addressed and grows
# one WAV per unique (voice, speed, text); without a cap it accreted unboundedly (409
# entries observed). Pruned LRU-by-mtime after each store, never evicting an in-use clip;
# `lookup` bumps mtime on a hit so the ordering is a true access-time LRU (IMP-038).
TTS_CACHE_MAX_BYTES = 512 * 1024 * 1024  # 512 MB


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
    """Return the cached WAV path if present, else None.

    On a hit, best-effort bump the file's mtime to now so `prune`'s "oldest mtime first"
    ordering is a true access-time LRU (a frequently replayed prompt keeps its slot) rather than
    LRU-by-creation — matching the `:13` comment (IMP-038). Failure to touch is non-fatal."""
    p = cache_path(voice, text, speed)
    if not p.exists():
        return None
    with contextlib.suppress(OSError):
        os.utime(p, None)  # refresh access-time recency
    return p


def store(voice: str | None, text: str, source_wav: Path, speed: float = 1.0) -> Path:
    """Copy a freshly synthesized WAV into the cache and return the cached path."""
    paths.ensure_dir(paths.tts_cache_dir())
    target = cache_path(voice, text, speed)
    if source_wav.resolve() == target.resolve():
        return target
    shutil.copyfile(source_wav, target)
    return target


def prune(max_bytes: int = TTS_CACHE_MAX_BYTES, *, keep: Path | None = None) -> int:
    """Evict least-recently-modified cached WAVs until the cache is under ``max_bytes``.

    Returns the number of files removed. Never evicts ``keep`` (the entry just stored, so a
    freshly-synthesized clip is never deleted before it is played — FR-021). Tolerant of a
    concurrent reader: a vanished file is skipped, and a read racing a delete surfaces the
    normal ``PlaybackError`` upstream (handled as today). A no-op when already under cap.
    """
    cache_dir = paths.tts_cache_dir()
    if not cache_dir.exists():
        return 0
    files: list[tuple[Path, int, float]] = []
    for f in cache_dir.iterdir():
        if not (f.is_file() and f.suffix == ".wav"):
            continue
        try:
            st = f.stat()
        except OSError:
            continue
        files.append((f, st.st_size, st.st_mtime))
    total = sum(size for _, size, _ in files)
    if total <= max_bytes:
        return 0
    keep_resolved = keep.resolve() if keep is not None else None
    files.sort(key=lambda t: t[2])  # oldest mtime first
    removed = 0
    for f, size, _ in files:
        if total <= max_bytes:
            break
        if keep_resolved is not None and f.resolve() == keep_resolved:
            continue
        try:
            f.unlink()
        except OSError:
            continue
        total -= size
        removed += 1
    return removed


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
