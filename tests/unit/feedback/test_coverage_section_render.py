"""IMP-026 — _coverage_section renders (never crashes) on a malformed pending report.

`build()` runs OUTSIDE resume's per-report try/except, so a hand-edited/truncated report with a
per-point missing `id`/`state` must render (skip the bad point / default to missed), not raise
`KeyError`/`ValueError` and abort the whole resume pass — even though `frontmatter.parse` is
deliberately tolerant.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import report_builder
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, Session

pytestmark = pytest.mark.unit


def _session(coverage, key_points=None) -> Session:
    return Session(
        session_id="2026-06-10-x", started_at=datetime(2026, 6, 10),
        question_id="x", question_text="Q", ideal_answer="A",
        attempts=[
            Attempt(ordinal=i, time_budget_seconds=60, actual_duration_seconds=10.0,
                    transcript=f"attempt {i}", metrics=AttemptMetrics())
            for i in (1, 2, 3)
        ],
        generated_by_phase="C", coverage=coverage, key_points=key_points,
    )


def test_coverage_section_renders_with_malformed_per_points():
    coverage = [
        {"attempt_ordinal": 1, "key_points_version": 1, "aggregate": 0.5,
         "per_point": [
             {"id": 1, "state": "covered"},
             {"id": 2},                            # missing state → defaults to "missed"
             {"id": "oops", "state": "covered"},    # non-int id → skipped, not int("oops")
             {"state": "partial"},                  # missing id → skipped
         ]},
        {"attempt_ordinal": 3, "key_points_version": 1, "aggregate": 1.0,
         "per_point": [{"id": 1, "state": "covered"}, {"id": 2, "state": "covered"}]},
    ]
    key_points = {"version": 1, "ideal_answer_hash": "abc", "points": [
        {"id": 1, "text": "kp one"},
        {"id": "bad", "text": "kp bad"},  # non-int id → skipped
        {"id": 2, "text": "kp two"},
    ]}
    # Previously KeyError on {"id": 2}'s missing state / ValueError on int("oops") / int("bad").
    body = report_builder.build(_session(coverage, key_points))
    assert "## Content coverage" in body
    assert "kp one" in body and "kp two" in body  # the valid points still render


def test_coverage_section_renders_with_no_keypoints_and_bad_ids():
    # No key_points → point_ids fall back to records[0].per_point (also guarded).
    coverage = [
        {"attempt_ordinal": 1, "key_points_version": 1, "aggregate": 0.0,
         "per_point": [{"id": 1, "state": "missed"}, {"id": "x"}]},  # non-int id + missing state
    ]
    body = report_builder.build(_session(coverage))
    assert "## Content coverage" in body
