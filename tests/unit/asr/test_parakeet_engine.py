"""T052 — Parakeet wrapper returns Transcript; silent input → is_empty True.

These tests stub `parakeet_mlx` to match the real 0.5.x public API:
    parakeet_mlx.from_pretrained(path) -> model
    model.transcribe(path) -> AlignedResult(text, sentences=[AlignedSentence(tokens=[AlignedToken(text, start, end, ...)])])
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field

import pytest

from speakloop.asr.interface import ASREngineError
from speakloop.asr.parakeet_engine import ParakeetEngine
from speakloop.installer.manifest import PARAKEET_TDT_06B_V3

pytestmark = pytest.mark.unit


@dataclass
class _FakeToken:
    text: str
    start: float
    end: float
    duration: float = 0.0
    confidence: float = 1.0
    id: int = 0


@dataclass
class _FakeSentence:
    text: str
    tokens: list
    start: float = 0.0
    end: float = 0.0
    duration: float = 0.0
    confidence: float = 1.0


@dataclass
class _FakeResult:
    text: str
    sentences: list = field(default_factory=list)


class _FakeModel:
    def __init__(self, response: _FakeResult):
        self._r = response

    def transcribe(self, path):  # real API takes a path string
        return self._r


def _install_fake_parakeet(monkeypatch, result: _FakeResult, tmp_path):
    # Pretend the model directory exists so ParakeetEngine._load() passes
    # its existence guard. The fake parakeet_mlx never reads the directory.
    models_dir = tmp_path / "models"
    (models_dir / PARAKEET_TDT_06B_V3.hf_repo_id.replace("/", "__")).mkdir(parents=True)
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(models_dir))

    fake_mod = types.ModuleType("parakeet_mlx")
    fake_mod.from_pretrained = lambda _path: _FakeModel(result)
    monkeypatch.setitem(sys.modules, "parakeet_mlx", fake_mod)


def test_transcribe_returns_expected_transcript(monkeypatch, wav_fixture, tmp_path):
    sentence = _FakeSentence(
        text="hello world",
        tokens=[_FakeToken("hello", 0.0, 0.5), _FakeToken("world", 0.6, 1.0)],
        start=0.0,
        end=1.0,
    )
    _install_fake_parakeet(
        monkeypatch,
        _FakeResult(text="hello world", sentences=[sentence]),
        tmp_path,
    )
    engine = ParakeetEngine()
    t = engine.transcribe(wav_fixture("attempt-short.wav"))
    assert t.text == "hello world"
    assert len(t.words) == 2
    assert t.words[0].word == "hello"
    assert t.audio_duration_seconds > 0


def test_silent_wav_yields_empty_transcript(monkeypatch, wav_fixture, tmp_path):
    _install_fake_parakeet(monkeypatch, _FakeResult(text="", sentences=[]), tmp_path)
    engine = ParakeetEngine()
    t = engine.transcribe(wav_fixture("attempt-silent.wav"))
    assert t.is_empty is True
    assert t.words == []


def test_unreadable_wav_raises(monkeypatch, tmp_path):
    _install_fake_parakeet(
        monkeypatch, _FakeResult(text="x", sentences=[]), tmp_path
    )
    engine = ParakeetEngine()
    with pytest.raises(ASREngineError):
        engine.transcribe(tmp_path / "does-not-exist.wav")
