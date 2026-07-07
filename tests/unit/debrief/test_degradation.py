"""T036 — graceful degradation + first-time guidance (US4: FR-028, FR-029, FR-030, SC-007).

Drives the full ``debrief.run`` orchestrator with a recording console and scripted
keypresses (no real tty, LLM/TTS stubbed). Proves SC-007: the menu is always
reached — when the LLM is absent (grammar placeholder) and when TTS raises mid
read-aloud — and that the first-time orientation line toggles on ``is_first_time``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from rich.console import Console

from speakloop.debrief import debrief
from speakloop.debrief.menu import DebriefChoice
from speakloop.debrief.renderer import FIRST_TIME_LINE, GRAMMAR_UNAVAILABLE_LINE
from speakloop.feedback import frontmatter

pytestmark = pytest.mark.unit


def _attempt(ordinal: int, transcript: str) -> frontmatter.Attempt:
    return frontmatter.Attempt(
        ordinal=ordinal,
        time_budget_seconds={1: 240, 2: 180, 3: 120}[ordinal],
        actual_duration_seconds={1: 235.0, 2: 175.0, 3: 118.0}[ordinal],
        transcript=transcript,
        metrics=frontmatter.AttemptMetrics(
            words_total=40,
            speech_rate_wpm=120.0,
            filler_words_count=2,
            filler_density_per_100_words=2.0,
            pauses_count=3,
            mean_pause_ms=500.0,
            self_corrections_count=0,
        ),
    )


def _phase_b_session() -> frontmatter.Session:
    """A Phase-B session: fluency-only narrative/top_priority, no grammar patterns."""
    return frontmatter.Session(
        session_id="2026-05-20-demo",
        started_at=datetime(2026, 5, 20, 9, 0),
        question_id="demo",
        question_text="Q",
        attempts=[
            _attempt(1, "one two three four five six seven eight nine ten eleven twelve"),
            _attempt(2, "short answer here"),
            _attempt(3, "another short one"),
        ],
        grammar_patterns=[],
        generated_by_phase="B",
        cross_attempt_narrative="Your speech rate held steady across the rounds.",
        top_priority="Reduce filler words next time.",
    )


def _recording_console() -> Console:
    return Console(width=200, record=True, force_terminal=True)


# --- FR-028: no-LLM branch renders the placeholder and still reaches the menu ---


def test_grammar_absent_shows_placeholder_and_reaches_menu(tmp_path: Path):
    console = _recording_console()
    choice = debrief.run(
        _phase_b_session(),
        sessions_dir=tmp_path,
        tts_engine=None,
        play_fn=None,
        no_audio=True,
        console=console,
        read_key=lambda: "q",
    )
    out = console.export_text()
    # The single grammar-unavailable line stands in for the patterns section.
    assert GRAMMAR_UNAVAILABLE_LINE in out
    # Fluency-only narrative + top priority are still shown.
    assert "speech rate held steady" in out
    assert "Reduce filler words" in out
    # SC-007: the menu was reached and returned a terminal choice.
    assert choice == DebriefChoice.QUIT


# --- FR-029: a TTS failure must still reach the menu without hanging ---


class _BoomTTS:
    def synthesize(self, _text, **_kwargs):
        raise RuntimeError("synth unavailable")


def test_tts_failure_still_reaches_menu(tmp_path: Path):
    console = _recording_console()
    plays: list[Path] = []
    choice = debrief.run(
        _phase_b_session(),
        sessions_dir=tmp_path,
        tts_engine=_BoomTTS(),
        play_fn=lambda p: plays.append(Path(p)),
        no_audio=False,  # audio path is exercised; it must swallow the error
        console=console,
        read_key=lambda: "q",
    )
    # The player swallowed the exception, so nothing ever played.
    assert plays == []
    # SC-007: control reached the menu despite the TTS failure (no hang).
    assert choice == DebriefChoice.QUIT


# --- FR-030: first-time orientation line toggles on is_first_time ---


class _FakeTTS:
    def synthesize(self, _text, **_kwargs):
        return Path("/dev/null")  # play_fn is a no-op stub; no real audio


def test_read_aloud_live_path_repaints_and_reaches_menu(tmp_path: Path):
    """IMP-014: on a real terminal (force_terminal → supports_live True) the read-aloud drives
    the rich.Live in-place repaint — every educational section fires on_section/live.update and
    the menu is still reached, with no crash."""
    console = _recording_console()  # force_terminal=True → supports_live(console) is True
    played: list[Path] = []
    choice = debrief.run(
        _phase_b_session(),  # narrative + top-priority → 2 audio sections, no grammar cards
        sessions_dir=tmp_path,
        tts_engine=_FakeTTS(),
        play_fn=lambda p: played.append(Path(p)),
        no_audio=False,
        console=console,
        read_key=lambda: "q",
    )
    assert choice == DebriefChoice.QUIT
    # Every section played through the Live path (one live.update each) without error.
    assert len(played) == 2


def test_first_time_line_shown_when_no_prior_report(tmp_path: Path):
    # Only this session's own report exists → first-time user.
    (tmp_path / "2026-05-20-demo.md").write_text("report", encoding="utf-8")
    console = _recording_console()
    debrief.run(
        _phase_b_session(),
        sessions_dir=tmp_path,
        tts_engine=None,
        play_fn=None,
        no_audio=True,
        console=console,
        read_key=lambda: "q",
    )
    assert FIRST_TIME_LINE in console.export_text()


def test_first_time_line_absent_for_returning_user(tmp_path: Path):
    # A prior report besides this session's own → returning user.
    (tmp_path / "2026-05-19-old.md").write_text("old", encoding="utf-8")
    (tmp_path / "2026-05-20-demo.md").write_text("report", encoding="utf-8")
    console = _recording_console()
    debrief.run(
        _phase_b_session(),
        sessions_dir=tmp_path,
        tts_engine=None,
        play_fn=None,
        no_audio=True,
        console=console,
        read_key=lambda: "q",
    )
    assert FIRST_TIME_LINE not in console.export_text()
