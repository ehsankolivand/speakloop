"""Per-pattern trend-series tests (010-interview-loop, T053)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from speakloop.trends.aggregator import aggregate, format_series
from speakloop.trends.reader import Report

pytestmark = pytest.mark.unit


def _report(date_str, patterns):
    return Report(
        path=Path(f"/x/{date_str}.md"),
        schema_version=1,
        session_id=f"{date_str}-q",
        started_at=datetime.fromisoformat(f"{date_str}T09:00:00"),
        question_id="q",
        attempts=[],
        grammar_patterns=[{"label": lbl, "occurrence_count": c} for lbl, c in patterns],
        generated_by_phase="C",
    )


def test_pattern_series_chronological():
    reports = [
        _report("2026-06-01", [("verb tense", 10)]),
        _report("2026-06-05", [("verb tense", 4)]),
        _report("2026-06-10", [("verb tense", 1)]),
    ]
    summary = aggregate(reports)
    series = summary.pattern_series["verb tense"]
    assert [c for _, c in series] == [10, 4, 1]
    assert format_series(series) == "10 → 4 → 1"


def test_format_series_single_point_has_no_arrow():
    reports = [_report("2026-06-10", [("article use", 3)])]
    summary = aggregate(reports)
    assert format_series(summary.pattern_series["article use"]) == "3"


def test_format_series_window_limits_length():
    reports = [_report(f"2026-06-0{i}", [("x", i)]) for i in range(1, 6)]
    summary = aggregate(reports)
    # window=3 keeps the last three counts
    assert format_series(summary.pattern_series["x"], window=3) == "3 → 4 → 5"
