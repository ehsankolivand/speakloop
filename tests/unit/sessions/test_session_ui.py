"""T016 — session_ui: countdown, control hints, ● REC indicator, summary. StringIO console."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop.feedback.frontmatter import Session
from speakloop.sessions import session_ui
from speakloop.sessions.session_ui import SessionState

pytestmark = pytest.mark.unit


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=100, force_terminal=False), buf


def test_countdown_emits_ticks_without_sleeping():
    console, buf = _console()
    slept: list[float] = []
    session_ui.countdown(console, ticks=3, interval=0.5, sleep=slept.append)
    out = buf.getvalue()
    assert "Recording in" in out
    assert "3" in out and "2" in out and "1" in out
    assert slept == [0.5, 0.5, 0.5]  # injected sleep, never the real clock


def test_control_hint_playing_shows_skip_and_replay():
    h = session_ui.control_hint(SessionState.PLAYING)
    assert "space" in h and "skip" in h and "replay" in h
    assert "skip follow-up" not in h


def test_control_hint_playing_follow_up_adds_skip_followup():
    h = session_ui.control_hint(SessionState.PLAYING, follow_up=True)
    assert "skip follow-up" in h


def test_control_hint_recording_shows_stop():
    h = session_ui.control_hint(SessionState.RECORDING)
    assert "stop" in h
    assert session_ui.control_hint(SessionState.RECORDING, follow_up=True).count("skip follow-up") == 1


def test_control_hint_transcribing_and_analyzing_have_no_keys():
    assert session_ui.control_hint(SessionState.TRANSCRIBING) == ""
    assert session_ui.control_hint(SessionState.ANALYZING) == ""


def test_recording_progress_renders_rec_marker_and_label():
    console, buf = _console()
    progress = session_ui.make_recording_progress(console)
    progress.add_task("rec", total=240, label="attempt 1")
    # Render the current frame as plain text (transient live display only emits to a
    # real terminal; the renderable is what the user sees).
    console.print(progress.get_renderable())
    out = buf.getvalue()
    assert "REC" in out
    assert "attempt 1" in out
    assert "240s" in out


def test_working_spinner_runs_and_clears():
    console, _ = _console()
    with session_ui.working(console, SessionState.ANALYZING, "Analyzing grammar…"):
        pass  # must not raise; transient


def _session(**kw) -> Session:
    from datetime import datetime

    return Session(
        session_id="2026-06-10-q01",
        started_at=datetime(2026, 6, 10),
        question_id="q01",
        question_text="q",
        attempts=[],
        **kw,
    )


def test_summary_graded_session_shows_grade_coverage_topfix_due():
    console, buf = _console()
    s = _session(
        answer_grade="good",
        top_priority="Use the article 'the' before singular nouns.",
        coverage=[
            {"attempt_ordinal": 1, "aggregate": 0.40},
            {"attempt_ordinal": 3, "aggregate": 0.85},
        ],
    )
    session_ui.render_summary(console, s, next_due="2026-06-13")
    out = buf.getvalue()
    assert "good" in out
    assert "40% → 85%" in out
    assert "Top fix" in out
    assert "2026-06-13" in out


def test_summary_tolerates_whitespace_only_top_priority():
    """A whitespace-only top_priority must not crash render_summary (review Finding B)."""
    console, buf = _console()
    session_ui.render_summary(console, _session(answer_grade="fair", top_priority="   \n  "))
    out = buf.getvalue()
    assert "fair" in out
    assert "Top fix" not in out  # no empty/garbage fix line


def test_summary_degraded_session_states_pending_not_a_fake_grade():
    console, buf = _console()
    s = _session(analysis_pending=True)
    session_ui.render_summary(console, s)
    out = buf.getvalue()
    assert "pending" in out.lower()
    # No coverage / fabricated grade for a degraded session.
    assert "→" not in out
