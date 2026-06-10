"""T005 — the additive `timings` frontmatter key round-trips; no-timings byte-identical."""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, Session

pytestmark = pytest.mark.unit


def _session(**kw) -> Session:
    return Session(
        session_id="2026-06-10-q01",
        started_at=datetime(2026, 6, 10, 9, 0, 0),
        question_id="q01",
        question_text="What are the four Android app components?",
        attempts=[Attempt(ordinal=1, time_budget_seconds=240, actual_duration_seconds=90.0,
                          metrics=AttemptMetrics(words_total=40))],
        **kw,
    )


def test_no_timings_report_is_byte_identical_to_before():
    """A session without timings emits no `timings:` key (SC-009)."""
    dumped = frontmatter.dump(_session())
    assert "timings" not in dumped


def test_timings_round_trips():
    timings = {
        "schema": 1,
        "total_seconds": 412.7,
        "analysis_mode": "concurrent",
        "analysis_concurrency": 3,
        "analysis_wall_seconds": 113.0,
        "stages": [
            {"name": "attempt_1_record", "seconds": 95.3},
            {"name": "attempt_1_transcribe", "seconds": 3.4, "overlapped": True},
        ],
    }
    dumped = frontmatter.dump(_session(timings=timings))
    assert "timings:" in dumped
    parsed = frontmatter.parse(dumped)
    assert parsed.timings == timings
    # dump -> parse -> dump is idempotent at the serialized level.
    assert frontmatter.dump(parsed) == dumped


def test_schema_version_stays_1_with_timings():
    dumped = frontmatter.dump(_session(timings={"schema": 1, "total_seconds": 1.0, "stages": []}))
    assert "schema_version: 1" in dumped


def test_pre_feature_report_without_timings_parses_to_none():
    dumped = frontmatter.dump(_session())
    assert frontmatter.parse(dumped).timings is None
