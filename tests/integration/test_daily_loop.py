"""Daily-loop end-to-end with stubs (010, T089): warm-up → attempts → coverage →
follow-ups → report; then store rebuild + resume of a pending session. No live audio."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.coverage.scoring import CoverageResult
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.sessions import coordinator
from speakloop.warmup.drill import DrillItem

pytestmark = pytest.mark.integration


class _StubTTS:
    def synthesize(self, text, voice=None):
        return Path("/dev/null")


class _StubASR:
    def __init__(self, attempt_text, followup_text):
        self._attempts = [Transcript(text=attempt_text) for _ in range(3)]
        self._followup = Transcript(text=followup_text)

    def transcribe(self, wav_path, *, context=None):
        return self._attempts.pop(0) if self._attempts else self._followup


def _record(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 4.0


def _grammar(transcripts):
    return [GrammarPattern(label="verb tense", occurrence_count=1,
                           evidence=[{"attempt_ordinal": 1, "quote": "is destroy", "corrected": "is destroyed"}])]


def _full_runners():
    return coordinator.Runners(
        mishearing=lambda real_text: [],
        followups=lambda q, ts: [{"question": "Why is the ViewModel retained?", "probe_ref": "ViewModel", "probe_type": "why"}],
        drill=lambda top: [DrillItem("Say it correctly.", "is destroyed", "is destroy")],
        keypoints=lambda q, ideal, qtype: [{"id": 1, "text": "kp one"}, {"id": 2, "text": "kp two"}],
        coverage=lambda kp, ts, ideal, version: CoverageResult(
            attempt_records=[
                {"attempt_ordinal": 1, "key_points_version": version, "aggregate": 0.5,
                 "per_point": [{"id": 1, "state": "covered"}, {"id": 2, "state": "missed"}]},
                {"attempt_ordinal": 3, "key_points_version": version, "aggregate": 1.0,
                 "per_point": [{"id": 1, "state": "covered"}, {"id": 2, "state": "covered"}]},
            ],
            content_errors=[],
            final_aggregate=1.0,
        ),
    )


def test_full_daily_loop_then_rebuild(tmp_sessions_dir, tmp_path):
    store_path = tmp_path / "store.json"
    # Seed a prior pattern so the warm-up has a qualifying top error.
    from speakloop.store import io as store_io
    from speakloop.store.model import Store
    seed = Store()
    seed.patterns["verb tense"] = [["2026-06-01", 4], ["2026-06-05", 3]]
    store_io.save_atomic(store_path, seed)

    result = coordinator.run_session(
        Question(id="rotation", question="Walk me through rotation.", ideal_answer="The activity is destroyed and recreated."),
        tts_engine=_StubTTS(),
        play_fn=lambda wav: None,
        asr_engine=_StubASR("the activity is destroy and recreate", "because it is in the retained instance"),
        record_fn=_record,
        grammar_analyzer=_grammar,
        runners=_full_runners(),
        store_path=store_path,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    )

    body = result.report_path.read_text()
    for section in ["## Warm-up drill", "## Content coverage", "## Follow-ups"]:
        assert section in body
    assert result.session.answer_grade == "strong"  # full coverage, no content errors, 1 grammar occ

    # Store advanced: schedule entry created, pattern folded.
    store = store_io.load(store_path)
    assert "rotation" in store.schedule
    assert store.schedule["rotation"].last_grade == "strong"
    assert "verb tense" in store.patterns

    # rebuild from the written report reproduces a store deterministically.
    from speakloop.store import rebuild as store_rebuild
    rebuilt = store_rebuild.rebuild(tmp_sessions_dir)
    assert "verb tense" in rebuilt.patterns


def test_resume_clears_pending(tmp_sessions_dir, tmp_path, monkeypatch):
    """A session written analysis-pending is finished by resume."""
    from datetime import datetime

    from speakloop.config import paths
    from speakloop.feedback import frontmatter, markdown_writer, report_builder
    from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, Session

    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_sessions_dir)
    monkeypatch.setattr(paths, "store_path", lambda: tmp_path / "store.json")

    pending = Session(
        session_id="2026-06-10-rotation", started_at=datetime(2026, 6, 10),
        question_id="rotation", question_text="Q", ideal_answer="A",
        attempts=[Attempt(ordinal=i, time_budget_seconds=b, actual_duration_seconds=10.0,
                          transcript=f"attempt {i} text the activity is destroy", metrics=AttemptMetrics())
                  for i, b in [(1, 240), (2, 180), (3, 120)]],
        generated_by_phase="B", analysis_pending=True, phase_c_error="LLMEngineError: down",
    )
    path = tmp_sessions_dir / "2026-06-10-rotation.md"
    markdown_writer.write_atomic(path, report_builder.build(pending))

    from speakloop.cli import practice, resume
    monkeypatch.setattr(practice, "_build_grammar_analyzer", lambda: _grammar)  # no .runners attr → coverage skipped

    resume.run(cloud=False)

    reloaded = frontmatter.parse(path.read_text())
    assert reloaded.analysis_pending is False
    assert reloaded.generated_by_phase == "C"
    assert len(reloaded.grammar_patterns) == 1
    assert reloaded.answer_grade is not None
