"""T029 — full practice loop → debrief → REPLAY with stubbed resident engines.

Drives `cli.practice.run` end to end with stubbed engines and scripted keypresses:
a session is run, the debrief renders, the menu choice REPLAY loops back to the
same question, and QUIT exits. Asserts SC-004's load-bearing property — the ASR
engine is constructed exactly ONCE (no model reload across replay) — and that
each replay writes a distinct report file.
"""

from __future__ import annotations

import json
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
    question: "Tell me about your experience."
    ideal_answer: "I have built mobile apps for years."
"""

_CANNED_LLM = json.dumps(
    {
        "patterns": [
            {
                "label": "3rd-person singular -s drop",
                "occurrence_count": 3,
                "evidence": [
                    {"attempt_ordinal": 1, "quote": "He write a function", "corrected": "He writes a function"}
                ],
            }
        ]
    }
)


def test_replay_loops_to_same_question_without_reload(
    monkeypatch, tmp_sessions_dir, tmp_qa_file, tmp_path
):
    tmp_qa_file.write_text(_QA, encoding="utf-8")

    asr_constructions = {"n": 0}

    class StubASR:
        def __init__(self):
            asr_constructions["n"] += 1

        def ensure_loaded(self):
            pass

        def transcribe(self, wav_path, *, context=None):
            return Transcript(
                text="He write a function. It run on dispatcher.", audio_duration_seconds=2.0
            )

    class StubLLM:
        def generate(self, *_a, **_k):
            return _CANNED_LLM

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

    from speakloop.feedback.grammar_analyzer import analyze

    # Stub everything that would touch a model or a device.
    monkeypatch.setattr("speakloop.asr.selection.WhisperMLXEngine", StubASR)
    monkeypatch.setattr(installer, "ensure_models", lambda *a, **k: None)
    monkeypatch.setattr(
        "speakloop.cli.practice._build_grammar_analyzer",
        lambda: (lambda ts: analyze(ts, StubLLM())),
    )
    monkeypatch.setattr(coordinator.recorder, "record", stub_record)

    # Scripted keypresses: listen advances on space (once); the menu replays
    # then quits. REPLAY skips the listen phase, so _read_key is called once.
    listen_keys = iter([" "])
    menu_keys = iter(["r", "q"])
    monkeypatch.setattr("speakloop.cli.practice._read_key", lambda: next(listen_keys))
    monkeypatch.setattr("speakloop.debrief.menu.read_key", lambda: next(menu_keys))

    plays: list = []
    from speakloop.cli import practice

    practice.run(
        question="demo",
        tts_engine=StubTTS(),
        play_fn=lambda p: plays.append(p),
        audio_devices=StubDevices,
    )

    # SC-004: engines constructed once before the loop → no reload on replay.
    assert asr_constructions["n"] == 1

    # Two sessions ran (original + one replay) → two distinct report files.
    reports = sorted(tmp_sessions_dir.glob("*.md"))
    assert len(reports) == 2
    assert reports[0].name != reports[1].name

    # Both reports are for the same question (REPLAY reused it) and are Phase C.
    for r in reports:
        text = r.read_text()
        assert "question_id: demo" in text
        assert "generated_by_phase: C" in text
        assert "3rd-person singular -s drop" in text
