"""T026 — engine selection + graceful fallback (FR-002/FR-009/SC-F).

Both engine classes are stubbed; no model load. build_engine probes the load
eagerly and falls back to Parakeet on failure with an English reason.
"""

from __future__ import annotations

import pytest

from speakloop.asr import selection
from speakloop.asr.interface import ASREngineError

pytestmark = pytest.mark.unit


class _OkEngine:
    def __init__(self):
        self.loaded = False

    def ensure_loaded(self):
        self.loaded = True

    def transcribe(self, wav_path, *, context=None):  # pragma: no cover
        ...


class _FailingEngine:
    def ensure_loaded(self):
        raise ASREngineError("model missing / OOM")

    def transcribe(self, wav_path, *, context=None):  # pragma: no cover
        ...


def _patch(monkeypatch, whisper_cls, parakeet_cls):
    monkeypatch.setattr(selection, "WhisperMLXEngine", whisper_cls)
    monkeypatch.setattr(selection, "ParakeetEngine", parakeet_cls)


def test_default_selects_whisper(monkeypatch):
    _patch(monkeypatch, _OkEngine, _OkEngine)
    sel = selection.build_engine()
    assert sel.engine_name == "whisper"
    assert sel.fell_back is False
    assert sel.fallback_reason is None
    assert sel.engine.loaded is True  # eagerly loaded
    assert "whisper-large-v3-turbo" in sel.model_id


def test_explicit_parakeet_has_no_fallback(monkeypatch):
    _patch(monkeypatch, _OkEngine, _OkEngine)
    sel = selection.build_engine("parakeet")
    assert sel.engine_name == "parakeet"
    assert sel.fell_back is False
    assert "parakeet" in sel.model_id


def test_whisper_load_failure_falls_back_to_parakeet(monkeypatch):
    _patch(monkeypatch, _FailingEngine, _OkEngine)
    sel = selection.build_engine()
    assert sel.engine_name == "parakeet"
    assert sel.fell_back is True
    assert isinstance(sel.fallback_reason, str) and sel.fallback_reason
    assert sel.engine.loaded is True


def test_explicit_whisper_failure_also_falls_back(monkeypatch):
    _patch(monkeypatch, _FailingEngine, _OkEngine)
    sel = selection.build_engine("whisper")
    assert sel.engine_name == "parakeet"
    assert sel.fell_back is True
