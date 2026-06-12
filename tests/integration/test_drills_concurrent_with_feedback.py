"""T024 (016) — the read-aloud drill block runs CONCURRENTLY with feedback, and the
combined report waits for both. No real model / mic / network.

Concurrency is proven deterministically: the grammar analyzer records the name of the
thread it ran on and we assert it ran on the background "speakloop-feedback" thread (so
the feedback truly ran off the main thread, while the drill block ran on the main thread).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.feedback.grammar_analyzer import analyze
from speakloop.pronunciation import load_drill_bank
from speakloop.pronunciation.interface import DrillResult, PhoneFlag
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
    return 0.5


class _FakeScorer:
    """Deterministic scorer: flags the /w/ in the first drill, clears the rest. Records the
    drill ids it scored so the test can assert the drill block actually ran."""

    def __init__(self):
        self.scored: list[str] = []

    def score(self, wav_path, *, canonical, targets, tip, competitors, drill_id, text, contrast_id):
        self.scored.append(drill_id)
        if len(self.scored) == 1:
            flag = PhoneFlag(
                expected=canonical[targets[0]["index"]] if targets else "w",
                word=text,
                gop=-3.0,
                competitor=(competitors[0] if competitors else None),
                competitor_margin=1.5,
                confident_diagnosis=True,
                tip=tip,
            )
            return DrillResult(drill_id, text, contrast_id, "scored", flags=[flag])
        return DrillResult(drill_id, text, contrast_id, "scored", flags=[])


class _StubLLM:
    def generate(self, *_a, **_k):
        return json.dumps(
            {
                "errors": [
                    {
                        "attempt_ordinal": 1,
                        "quote": "He write a function",
                        "corrected": "He writes a function",
                        "error_type": "3rd-person singular -s drop",
                        "explanation": "Third-person singular present verbs take -s.",
                    }
                ]
            }
        )


def test_drills_run_concurrently_with_feedback_and_merge_into_one_report(
    tmp_sessions_dir, tmp_path
):
    transcripts = [
        Transcript(text="He write a function.", audio_duration_seconds=2.0),
        Transcript(text="It run on dispatcher.", audio_duration_seconds=2.0),
        Transcript(text="A coroutine run.", audio_duration_seconds=2.0),
    ]
    captured: dict = {}

    def grammar_runner(ts):
        captured["thread"] = threading.current_thread().name
        time.sleep(0.05)  # widen the overlap window with the drill block
        return analyze(ts, _StubLLM())

    grammar_runner.engine = type("E", (), {"parallel_safe": True})()  # mark cloud-like

    scorer = _FakeScorer()
    drills = coordinator.PronunciationDrills(
        scorer=scorer, bank=load_drill_bank(), engine_note="offered because the local model isn't resident"
    )

    q = Question(id="kotlin-coroutines-basics", question="Q", ideal_answer="A")
    result = coordinator.run_session(
        q,
        asr_engine=_StubASR(transcripts),
        record_fn=_stub_record,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
        grammar_analyzer=grammar_runner,
        analysis_parallel_safe=True,
        analysis_concurrency=3,
        pronunciation_drills=drills,
    )

    # (concurrency) the feedback ran on the background thread, not inline:
    assert captured["thread"] == "speakloop-feedback"
    # (drill block ran) the scorer was invoked for at least the base drills:
    assert scorer.scored, "the drill block never scored a drill"

    report = result.report_path.read_text()
    # (merged) the report contains BOTH the grammar output AND the pronunciation section:
    assert "3rd-person singular -s drop" in report
    assert "## Pronunciation drills" in report
    # (calibrated) the flagged drill leads with detection and hedges the diagnosis:
    assert "sounded off" in report
    assert "suggestion" in report

    # (waited for both) the in-memory session carries the drill results:
    assert result.session.pronunciation_drills is not None
    assert result.session.pronunciation_drills["summary"]["with_flags"] >= 1

    # (privacy) drill WAVs are discarded after scoring — none left in scratch.
    leftover = list((tmp_path / "scratch").glob("drill-*.wav"))
    assert leftover == [], f"drill audio left on disk: {leftover}"


def test_no_drills_bundle_keeps_today_inline_path(tmp_sessions_dir, tmp_path):
    # Without a bundle, analysis runs inline (main thread) — the byte-identical legacy path.
    transcripts = [Transcript(text=f"attempt {i}", audio_duration_seconds=2.0) for i in (1, 2, 3)]
    captured: dict = {}

    def grammar_runner(ts):
        captured["thread"] = threading.current_thread().name
        return []

    q = Question(id="kotlin-coroutines-basics", question="Q", ideal_answer="A")
    result = coordinator.run_session(
        q,
        asr_engine=_StubASR(transcripts),
        record_fn=_stub_record,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
        grammar_analyzer=grammar_runner,
    )
    assert captured["thread"] == threading.main_thread().name  # inline, not backgrounded
    assert result.session.pronunciation_drills is None
    assert "## Pronunciation drills" not in result.report_path.read_text()
