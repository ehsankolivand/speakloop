"""T040 — the ASR model loads once across attempts + replay (guards SC-D).

Drives `cli.practice.run` through a session and a REPLAY (3 attempts each) and
asserts the engine is constructed once and `ensure_loaded` is called exactly once
— the warm-model property the 5 s per-attempt budget depends on (research §c).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop import installer
from speakloop.asr import Transcript
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration

_QA = """\
schema_version: 1
questions:
  - id: demo
    question: "Explain Kotlin coroutines versus threads."
    ideal_answer: "Coroutines run on a shared pool of threads."
"""


def test_model_loaded_once_across_attempts_and_replay(
    monkeypatch, tmp_sessions_dir, tmp_qa_file, tmp_path
):
    tmp_qa_file.write_text(_QA, encoding="utf-8")
    counters = {"constructions": 0, "loads": 0, "transcribes": 0}

    class CountingWhisper:
        def __init__(self):
            counters["constructions"] += 1

        def ensure_loaded(self):
            counters["loads"] += 1

        def transcribe(self, wav_path, *, context=None):
            counters["transcribes"] += 1
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

    monkeypatch.setattr("speakloop.asr.selection.WhisperMLXEngine", CountingWhisper)
    monkeypatch.setattr(installer, "ensure_models", lambda *a, **k: None)
    from speakloop.cli import practice as _practice

    monkeypatch.setattr(
        "speakloop.cli.practice._build_grammar_analyzer", lambda: _practice._NO_ANALYSIS
    )
    monkeypatch.setattr(coordinator.recorder, "record", stub_record)

    listen_keys = iter([" "])
    menu_keys = iter(["r", "q"])  # one replay, then quit
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

    assert counters["constructions"] == 1  # built once before the loop
    assert counters["loads"] == 1  # warmed once; never reloaded on replay (SC-D)
    assert counters["transcribes"] == 6  # 3 attempts × 2 sessions, all on the warm model
