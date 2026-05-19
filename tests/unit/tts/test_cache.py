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
