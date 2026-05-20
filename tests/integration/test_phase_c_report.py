"""T084 — full session with stub LLM produces a Phase-C report."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.feedback.grammar_analyzer import analyze
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration


class _StubASR:
    def __init__(self, transcripts):
        self._iter = iter(transcripts)

    def transcribe(self, wav_path, *, context=None):
        return next(self._iter)


def _stub_record(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 1.0


def test_phase_c_report_has_grammar_patterns(tmp_sessions_dir, tmp_path):
    transcripts = [
        Transcript(text="He write a function. It run on dispatcher.", audio_duration_seconds=2.0),
        Transcript(text="The system handle thousands of users.", audio_duration_seconds=2.0),
        Transcript(
            text="A coroutine run on dispatcher. He listen to music.", audio_duration_seconds=2.0
        ),
    ]
    canned = json.dumps(
        {
            "patterns": [
                {
                    "label": "3rd-person singular -s drop",
                    "occurrence_count": 5,
                    "evidence": [
                        {"attempt_ordinal": 1, "quote": "He write a function"},
                        {"attempt_ordinal": 2, "quote": "The system handle"},
                        {"attempt_ordinal": 3, "quote": "A coroutine run"},
                    ],
                    "suggested_fix": "He writes / it runs / handles / listens.",
                }
            ]
        }
    )

    class StubLLM:
        def generate(self, *_a, **_k):
            return canned

    def grammar_runner(ts):
        return analyze(ts, StubLLM())

    q = Question(id="kotlin-coroutines-basics", question="Q", ideal_answer="A")
    start = time.monotonic()
    path = coordinator.run_session(
        q,
        asr_engine=_StubASR(transcripts),
        record_fn=_stub_record,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
        grammar_analyzer=grammar_runner,
    ).report_path
    elapsed = time.monotonic() - start

    fm = yaml.safe_load(path.read_text().split("---\n", 2)[1])
    assert fm["generated_by_phase"] == "C"
    assert len(fm["grammar_patterns"]) == 1
    assert fm["grammar_patterns"][0]["label"] == "3rd-person singular -s drop"

    # SC-003 (on the mock path, must be < 60 s — actually milliseconds here).
    assert elapsed < 60.0
