"""Interval-ladder + mastery tests (010-interview-loop, T050) — table-driven."""

from __future__ import annotations

from datetime import date

import pytest

from speakloop.srs import schedule
from speakloop.store.model import ScheduleEntry

pytestmark = pytest.mark.unit

TODAY = date(2026, 6, 10)


def _entry(**kw):
    base = dict(question_id="q", interval_days=4, consecutive_strong=0, mastered=False)
    base.update(kw)
    return ScheduleEntry(**base)


@pytest.mark.parametrize(
    ("grade", "prev_interval", "expected_interval"),
    [
        ("poor", 8, 1),    # reset to base
        ("fair", 8, 2),
        ("good", 4, 8),    # ×2
        ("good", 20, 21),  # capped at 21
        ("strong", 4, 10),  # ×2.5
        ("strong", 10, 21),  # capped
    ],
)
def test_interval_ladder(grade, prev_interval, expected_interval):
    out = schedule.next_due(_entry(interval_days=prev_interval), grade, today=TODAY)
    assert out.interval_days == expected_interval
    assert out.last_grade == grade
    assert out.total_reviews == 1


def test_poor_resurfaces_within_one_day():
    out = schedule.next_due(_entry(interval_days=12), "poor", today=TODAY)
    assert out.next_due == "2026-06-11"


def test_fair_resurfaces_within_two_days():
    out = schedule.next_due(_entry(), "fair", today=TODAY)
    assert out.next_due == "2026-06-12"


def test_two_consecutive_strong_masters():
    e1 = schedule.next_due(_entry(interval_days=2, consecutive_strong=0), "strong", today=TODAY)
    assert e1.mastered is False and e1.consecutive_strong == 1
    e2 = schedule.next_due(e1, "strong", today=TODAY)
    assert e2.mastered is True
    assert e2.interval_days == 30  # maintenance ceiling


def test_non_strong_demotes_a_mastered_question():
    mastered = _entry(interval_days=30, consecutive_strong=2, mastered=True)
    out = schedule.next_due(mastered, "good", today=TODAY)
    assert out.mastered is False
    assert out.interval_days == 2  # demoted to base ladder, good → base×2


# --- 018: the shared `advance()` ladder used by both questions and line-cards ---------


@pytest.mark.parametrize("grade", ["poor", "fair", "good", "strong"])
@pytest.mark.parametrize(
    ("prev", "consecutive", "mastered"),
    [
        (0, 0, False),   # never-reviewed card (interval 0 normalises to base)
        (4, 0, False),
        (10, 1, False),  # one strong already
        (30, 2, True),   # a mastered item (demotion path when non-strong)
    ],
)
def test_advance_matches_next_due(grade, prev, consecutive, mastered):
    """`advance()` reproduces `next_due`'s interval/streak/mastery — the extraction is
    behaviour-preserving and is the one ladder both schedulers share (018 D2)."""
    entry = ScheduleEntry(
        question_id="q", interval_days=prev, consecutive_strong=consecutive, mastered=mastered
    )
    via_next_due = schedule.next_due(entry, grade, today=TODAY)
    result = schedule.advance(prev, consecutive, mastered, grade)
    assert result.interval_days == via_next_due.interval_days
    assert result.consecutive_strong == via_next_due.consecutive_strong
    assert result.mastered == via_next_due.mastered


def test_advance_normalises_zero_interval_to_base():
    # a fresh card with interval 0 graded good → base(1) × 2 = 2 (not 0)
    assert schedule.advance(0, 0, False, "good").interval_days == 2
