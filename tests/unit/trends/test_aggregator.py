"""T093 — trends.aggregator."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.trends import aggregator, reader

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parents[2] / "fixtures" / "sessions"


def test_totals_and_date_range():
    result = reader.read_reports(FIXTURES)
    summary = aggregator.aggregate(result.reports)
    assert summary.total_sessions == 3
    assert summary.date_range[0].isoformat() == "2026-05-15"
    assert summary.date_range[1].isoformat() == "2026-05-18"


def test_metric_series_uses_attempt_three():
    result = reader.read_reports(FIXTURES)
    summary = aggregator.aggregate(result.reports)
    wpm = summary.metric_series["speech_rate_wpm"]
    assert len(wpm) == 3
    # Sorted chronologically (reader uses sorted glob).
    assert wpm[0][1] == 105.0  # 2026-05-15 attempt-3
    assert wpm[-1][1] == 115.0  # 2026-05-18 attempt-3


def test_pattern_ranking_descending_with_tie_break():
    result = reader.read_reports(FIXTURES)
    summary = aggregator.aggregate(result.reports, top_n=10)
    labels = [row.label for row in summary.pattern_ranking]
    # 3rd-person singular -s drop: 4 + 3 = 7
    # definite-article omission: 2
    # preposition substitution: 2 (tie with article — sorted alphabetically asc).
    assert labels[0] == "3rd-person singular -s drop"
    assert labels[1] == "definite-article omission"  # alphabetic before "preposition…"
    assert labels[2] == "preposition substitution"


def test_top_n_truncates():
    result = reader.read_reports(FIXTURES)
    summary = aggregator.aggregate(result.reports, top_n=1)
    assert len(summary.pattern_ranking) == 1
