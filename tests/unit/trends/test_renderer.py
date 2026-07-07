"""T094 — trends.renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.trends import aggregator, reader, renderer

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parents[2] / "fixtures" / "sessions"


def test_empty_state_friendly():
    out = renderer.render(aggregator.TrendsSummary())
    assert "No session reports" in out
    assert "speakloop practice" in out


def test_populated_summary_renders():
    result = reader.read_reports(FIXTURES)
    summary = aggregator.aggregate(result.reports)
    out = renderer.render(summary)
    assert "Total sessions:" in out
    assert "3rd-person singular -s drop" in out
    # SC-008 sanity: 3 sessions render in well under 60 lines.
    assert out.count("\n") < 60


def test_sc_008_line_count_for_10_sessions():
    """SC-008: ≤ 60 lines for 10 sessions (use synthetic Report list)."""
    from datetime import datetime

    from speakloop.trends.reader import Report

    reports = [
        Report(
            path=Path(f"r{i}.md"),
            schema_version=1,
            session_id=f"2026-05-{i:02d}-q1",
            started_at=datetime(2026, 5, i),
            question_id="q1",
            attempts=[
                {
                    "ordinal": 3,
                    "time_budget_seconds": 120,
                    "actual_duration_seconds": 120,
                    "metrics": {
                        "speech_rate_wpm": 100.0 + i,
                        "filler_density_per_100_words": 3.0,
                        "pauses_count": 8,
                        "mean_pause_ms": 400,
                        "self_corrections_count": 2,
                    },
                }
            ],
            grammar_patterns=[{"label": "3rd-person singular -s drop", "occurrence_count": 3}],
            generated_by_phase="C",
        )
        for i in range(1, 11)
    ]
    summary = aggregator.aggregate(reports)
    out = renderer.render(summary)
    assert out.count("\n") <= 60


def test_metric_labels_are_friendly_and_delta_is_direction_aware():
    """IMP-042: raw METRIC_KEYS are replaced by human labels, and the Δ is annotated with the
    better/worse direction (fewer fillers is better even as the number falls; more pauses is
    worse even as the number rises)."""
    from datetime import date

    summary = aggregator.TrendsSummary(
        total_sessions=2, date_range=("2026-05-01", "2026-05-02"),
        metric_series={
            "speech_rate_wpm": [(date(2026, 5, 1), 100.0), (date(2026, 5, 2), 120.0)],
            "filler_density_per_100_words": [(date(2026, 5, 1), 5.0), (date(2026, 5, 2), 2.0)],
            "pauses_count": [(date(2026, 5, 1), 8.0), (date(2026, 5, 2), 10.0)],
        },
        pattern_ranking=[], pattern_series={},
    )
    out = renderer.render(summary)
    assert "Speech rate (WPM)" in out and "speech_rate_wpm" not in out  # friendly, not snake_case
    assert "+20.0 (better)" in out   # WPM up = better
    assert "-3.0 (better)" in out     # fillers down = better
    assert "+2.0 (worse)" in out      # pauses up = worse (the fix — a +Δ that's a regression)
