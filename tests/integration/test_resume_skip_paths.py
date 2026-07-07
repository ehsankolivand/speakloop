"""IMP-023 — resume.py robustness skip paths + `_extract_attempt_transcripts`.

`cli/CLAUDE.md` calls these load-bearing: a corrupt pending report must not masquerade as
"nothing to resume", and a report whose analysis fails again must stay pending (never falsely
resolved). Previously only the happy path (`test_resume_clears_pending`) was covered.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.cli import resume
from speakloop.feedback import frontmatter, markdown_writer, report_builder
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, GrammarPattern, Session

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_sessions_dir, tmp_path, monkeypatch):
    from speakloop.config import paths

    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_sessions_dir)
    monkeypatch.setattr(paths, "store_path", lambda: tmp_path / "store.json")
    return tmp_sessions_dir


def _pending_report() -> str:
    s = Session(
        session_id="2026-06-10-rotation", started_at=datetime(2026, 6, 10),
        question_id="rotation", question_text="Q", ideal_answer="A",
        attempts=[
            Attempt(ordinal=i, time_budget_seconds=b, actual_duration_seconds=10.0,
                    transcript=f"attempt {i} the activity is destroy", metrics=AttemptMetrics())
            for i, b in [(1, 240), (2, 180), (3, 120)]
        ],
        generated_by_phase="B", analysis_pending=True, phase_c_error="LLMEngineError: down",
    )
    return report_builder.build(s)


def _grammar_ok(transcripts):
    return [GrammarPattern(label="verb tense", occurrence_count=1,
                           evidence=[{"attempt_ordinal": 1, "quote": "is destroy", "corrected": "is destroyed"}])]


def _patch_grammar(monkeypatch, runner):
    from speakloop.cli import practice

    monkeypatch.setattr(
        practice, "_build_grammar_analyzer",
        lambda: practice.GrammarAnalysis(runner=runner, runners=None, engine=None, coach=None),
    )


def _norm(capsys) -> str:
    # Collapse rich's soft-wrap newlines so phrase matching is robust to the console width.
    return " ".join(capsys.readouterr().out.split())


def test_unreadable_report_is_warned_and_skipped(_isolate_paths, capsys):
    # Malformed YAML frontmatter → frontmatter.parse raises in the pending scan.
    (_isolate_paths / "2026-06-10-corrupt.md").write_text("---\nfoo: [1, 2\n---\nbody", encoding="utf-8")
    resume.run(cloud=False)
    out = _norm(capsys)
    assert "unreadable report frontmatter" in out and "skipping" in out
    # It never became a pending candidate → the scan reports nothing to resume.
    assert "No analysis-pending sessions" in out


def test_pending_report_with_no_transcripts_is_skipped(_isolate_paths, capsys, monkeypatch):
    # A valid pending report whose body has no ## Transcripts section → no recoverable transcripts.
    no_transcripts = _pending_report().split("## Transcripts", 1)[0].rstrip() + "\n"
    path = _isolate_paths / "2026-06-10-rotation.md"
    path.write_text(no_transcripts, encoding="utf-8")
    _patch_grammar(monkeypatch, _grammar_ok)  # never called — the report is skipped first
    resume.run(cloud=False)
    assert "no transcripts found" in _norm(capsys)
    # Left pending — never falsely marked done.
    assert frontmatter.parse(path.read_text()).analysis_pending is True


def test_analysis_failing_again_leaves_report_pending(_isolate_paths, capsys, monkeypatch):
    path = _isolate_paths / "2026-06-10-rotation.md"
    markdown_writer.write_atomic(path, _pending_report())

    def _boom(transcripts):
        raise RuntimeError("model still down")

    _patch_grammar(monkeypatch, _boom)
    resume.run(cloud=False)
    assert "analysis still failing" in _norm(capsys)
    reloaded = frontmatter.parse(path.read_text())
    assert reloaded.analysis_pending is True  # NOT falsely resolved
    assert reloaded.generated_by_phase == "B"


def test_extract_attempt_transcripts_silent_mapping_and_section_boundary():
    body = (
        "## Grammar\nsome grammar text\n\n"
        "## Transcripts\n\n"
        "### Attempt 1\n\nhello world here\n\n"
        "### Attempt 2\n\n_(silent)_\n\n"
        "### Attempt 3\n\nthird attempt text\n\n"
        "## Something After\nnot a transcript, must be ignored\n"
    )
    got = resume._extract_attempt_transcripts(body)
    assert got == {1: "hello world here", 2: "", 3: "third attempt text"}
