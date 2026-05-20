"""T013 — WhisperMLXEngine forwards biasing/decoding options to mlx_whisper.

Stubs the `mlx_whisper` module (no model load) and asserts the engine forwards
initial_prompt, language="en", condition_on_previous_text=False, and
word_timestamps=True, and maps the result dict to a Transcript (research §S1).
"""

from __future__ import annotations

import sys
import types

import pytest

from speakloop.asr import TranscriptionContext
from speakloop.asr.whisper_mlx_engine import WhisperMLXEngine

pytestmark = pytest.mark.integration


def _install_fake_mlx_whisper(monkeypatch, captured: dict):
    fake = types.ModuleType("mlx_whisper")

    def _transcribe(audio, **kwargs):
        captured["audio"] = audio
        captured.update(kwargs)
        return {
            "text": "coroutines run on a shared pool of threads",
            "segments": [
                {
                    "words": [
                        {"word": " coroutines", "start": 0.0, "end": 0.5},
                        {"word": " threads", "start": 0.6, "end": 0.9},
                    ]
                }
            ],
        }

    fake.transcribe = _transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake)


def test_forwards_initial_prompt_and_decoding_options(monkeypatch, wav_fixture):
    captured: dict = {}
    _install_fake_mlx_whisper(monkeypatch, captured)

    engine = WhisperMLXEngine()
    # Bypass the heavy model load; we only test the transcribe call path.
    monkeypatch.setattr(engine, "_load", lambda: None)

    ctx = TranscriptionContext(
        initial_prompt="The following is technical English spoken with a Persian accent. coroutines",
        initial_prompt_sha256="abc123",
        use_vad=False,  # exercise the no-VAD path in US1
    )
    t = engine.transcribe(wav_fixture("attempt-short.wav"), context=ctx)

    assert captured["initial_prompt"] == ctx.initial_prompt
    assert captured["language"] == "en"
    assert captured["condition_on_previous_text"] is False
    assert captured["word_timestamps"] is True
    assert "whisper-large-v3-turbo" in captured["path_or_hf_repo"]

    assert t.text == "coroutines run on a shared pool of threads"
    assert [w.word for w in t.words] == ["coroutines", "threads"]
    assert t.audio_duration_seconds > 0


def test_no_initial_prompt_when_context_has_none(monkeypatch, wav_fixture):
    captured: dict = {}
    _install_fake_mlx_whisper(monkeypatch, captured)
    engine = WhisperMLXEngine()
    monkeypatch.setattr(engine, "_load", lambda: None)

    # use_vad=False exercises the whole-clip path; a None initial_prompt forwards as None.
    engine.transcribe(
        wav_fixture("attempt-short.wav"),
        context=TranscriptionContext(use_vad=False),
    )
    assert captured["initial_prompt"] is None
    assert captured["language"] == "en"
