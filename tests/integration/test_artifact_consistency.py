"""Artifact-consistency guarantee through the coordinator (010, T074 / SC-004).

A generated coaching artifact that contradicts the ideal answer is corrected or
dropped BEFORE the report is written — the contradiction never reaches the report.
Stubbed engines — no live models.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration

_IDEAL = "It throws IllegalStateException after onSaveInstanceState."
_BAD_COACHING = "## Your answer, improved\nIt throws NullPointerException after onSaveInstanceState."


class _StubASR:
    def transcribe(self, wav_path, *, context=None):
        return Transcript(text="it throws an exception after on save instance state")


def _record(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 3.0


def _grammar(transcripts):
    return [GrammarPattern(label="article use", occurrence_count=1,
                           evidence=[{"attempt_ordinal": 1, "quote": "throws an exception"}])]


def _run(consistency_fn, tmp_sessions_dir, tmp_path):
    runners = coordinator.Runners(consistency=consistency_fn)
    return coordinator.run_session(
        Question(id="q", question="Q", ideal_answer=_IDEAL),
        asr_engine=_StubASR(),
        record_fn=_record,
        grammar_analyzer=_grammar,
        coach=lambda q, transcripts, patterns: _BAD_COACHING,  # contradictory artifact
        runners=runners,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    )


def test_contradiction_dropped_when_uncorrectable(tmp_sessions_dir, tmp_path):
    # consistency returns None → the artifact is withheld
    result = _run(lambda artifact, ideal: None, tmp_sessions_dir, tmp_path)
    assert result.session.coaching is None
    assert "NullPointerException" not in result.report_path.read_text()
    assert result.session.coach_error  # a non-fatal note is recorded


def test_contradiction_corrected_when_fixable(tmp_sessions_dir, tmp_path):
    fixed = "## Your answer, improved\nIt throws IllegalStateException after onSaveInstanceState."
    result = _run(lambda artifact, ideal: fixed, tmp_sessions_dir, tmp_path)
    body = result.report_path.read_text()
    assert "IllegalStateException" in body
    assert "NullPointerException" not in body
