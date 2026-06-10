"""T009 — TTS cache invalidation (hash-keyed) + size-capped LRU prune."""

from __future__ import annotations

import os

import pytest

from speakloop.tts import cache

pytestmark = pytest.mark.unit


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    d = tmp_path / "ttscache"
    d.mkdir()
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(d))
    return d


def _write(path, size_bytes, mtime):
    path.write_bytes(b"\0" * size_bytes)
    os.utime(path, (mtime, mtime))


def test_text_change_invalidates_key(cache_dir):
    """Different text → different key → old audio not reused (FR-020)."""
    k1 = cache.cache_key("af_heart", "the four components", 0.85)
    k2 = cache.cache_key("af_heart", "the four components!", 0.85)
    assert k1 != k2
    # Speed folded in only when != 1.0; default speed keeps the historical formula.
    assert cache.cache_key("af_heart", "x") == cache.cache_key("af_heart", "x", 1.0)


def test_prune_noop_under_cap(cache_dir):
    _write(cache_dir / "a.wav", 100, mtime=1000)
    assert cache.prune(max_bytes=1000) == 0
    assert (cache_dir / "a.wav").exists()


def test_prune_evicts_oldest_until_under_cap(cache_dir):
    _write(cache_dir / "old.wav", 100, mtime=1000)
    _write(cache_dir / "mid.wav", 100, mtime=2000)
    _write(cache_dir / "new.wav", 100, mtime=3000)
    # cap 250 bytes → must drop the single oldest (100) to reach 200.
    removed = cache.prune(max_bytes=250)
    assert removed == 1
    assert not (cache_dir / "old.wav").exists()
    assert (cache_dir / "mid.wav").exists()
    assert (cache_dir / "new.wav").exists()


def test_prune_never_evicts_kept_entry(cache_dir):
    _write(cache_dir / "old.wav", 100, mtime=1000)  # oldest, but it's the just-stored one
    _write(cache_dir / "new.wav", 100, mtime=3000)
    removed = cache.prune(max_bytes=100, keep=cache_dir / "old.wav")
    # Must evict new.wav (not the kept old.wav) even though old is older.
    assert removed == 1
    assert (cache_dir / "old.wav").exists()
    assert not (cache_dir / "new.wav").exists()


def test_prune_tolerates_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(tmp_path / "does-not-exist"))
    assert cache.prune(max_bytes=10) == 0
