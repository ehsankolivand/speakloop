"""T027 — graceful fallback to Parakeet when Whisper cannot load (FR-009/SC-F).

Drives `cli.practice.run`: the Whisper stub fails to load, selection falls back
to the Parakeet stub, the session completes, exactly one English fallback line is
printed, and the report records engine: parakeet / fell_back: true.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop import installer
from speakloop.asr import Transcript
from speakloop.asr.interface import ASREngineError
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration

_QA = """\
schema_version: 1
questions:
  - id: demo
    question: "Explain Kotlin coroutines versus threads."
    ideal_answer: "Coroutines run on a shared pool of threads."
"""


def test_whisper_load_failure_falls_back_to_parakeet(
    monkeypatch, capsys, tmp_sessions_dir, tmp_qa_file, tmp_path
):
    tmp_qa_file.write_text(_QA, encoding="utf-8")

    class FailingWhisper:
        def ensure_loaded(self):
            raise ASREngineError("Whisper model not found")

        def transcribe(self, wav_path, *, context=None):  # pragma: no cover
            raise AssertionError("Whisper must not be used after a failed load")

    class StubParakeet:
        def ensure_loaded(self):
            pass

        def transcribe(self, wav_path, *, context=None):
            return Transcript(text="coroutines run on threads", audio_duration_seconds=2.0)

    class StubTTS:
        def synthesize(self, text, voice=None):
            p = tmp_path / "clip.wav"
            p.write_bytes(b"\x00")
            return p

    class StubDevices:
        @staticmethod
        def default_input():
            return "mic-0"

    def stub_record(out_path, time_budget_seconds, early_exit_event):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00")
        return 1.0

    monkeypatch.setattr("speakloop.asr.selection.WhisperMLXEngine", FailingWhisper)
    monkeypatch.setattr("speakloop.asr.selection.ParakeetEngine", StubParakeet)
    monkeypatch.setattr(installer, "ensure_models", lambda *a, **k: None)
    monkeypatch.setattr("speakloop.cli.practice._build_grammar_analyzer", lambda: None)
    monkeypatch.setattr(coordinator.recorder, "record", stub_record)

    listen_keys = iter([" "])
    menu_keys = iter(["q"])
    monkeypatch.setattr("speakloop.cli.practice._read_key", lambda: next(listen_keys))
    monkeypatch.setattr("speakloop.debrief.menu.read_key", lambda: next(menu_keys))

    from speakloop.cli import practice

    practice.run(
        question="demo",
        no_audio=True,
        tts_engine=StubTTS(),
        play_fn=lambda p: None,
        audio_devices=StubDevices,
    )

    out = capsys.readouterr().out.lower()
    assert "parakeet" in out  # the one-line fallback notice names the fallback engine

    reports = sorted(tmp_sessions_dir.glob("*.md"))
    assert len(reports) == 1
    text = reports[0].read_text()
    assert "engine: parakeet" in text
    assert "fell_back: true" in text
