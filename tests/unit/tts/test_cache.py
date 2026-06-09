"""T039 — TTS clip cache contract."""

from __future__ import annotations

import hashlib

import pytest

from speakloop.tts import cache

pytestmark = pytest.mark.unit


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(tmp_path / "tts"))
    yield tmp_path / "tts"


def test_cache_key_is_sha256(tmp_cache_dir):
    voice = "bm_george"
    text = "hello world"
    expected = hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()
    assert cache.cache_key(voice, text) == expected


def test_default_speed_key_is_backward_compatible(tmp_cache_dir):
    # speed=1.0 must NOT change the historical key formula, so existing
    # default-speed cache entries keep hitting.
    assert cache.cache_key("bm_george", "hi", 1.0) == cache.cache_key("bm_george", "hi")


def test_slower_speed_yields_distinct_key(tmp_cache_dir):
    base = cache.cache_key("bm_george", "hi")
    slow = cache.cache_key("bm_george", "hi", 0.7)
    assert slow != base
    # And different non-default speeds are distinct from each other.
    assert slow != cache.cache_key("bm_george", "hi", 0.85)


def test_lookup_miss_returns_none(tmp_cache_dir):
    assert cache.lookup("bm_george", "never seen") is None


def test_store_then_lookup_returns_path(tmp_cache_dir, wav_fixture):
    src = wav_fixture("test-clip.wav")
    target = cache.store("bm_george", "hello", src)
    assert target.exists()
    assert target == cache.lookup("bm_george", "hello")


def test_same_inputs_yield_same_path(tmp_cache_dir):
    a = cache.cache_path(None, "hi")
    b = cache.cache_path(None, "hi")
    assert a == b
