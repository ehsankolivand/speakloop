"""Due-queue tests (010-interview-loop, T051)."""

from __future__ import annotations

from datetime import date

import pytest

from speakloop.srs.queue import due_queue
from speakloop.store.model import ScheduleEntry

pytestmark = pytest.mark.unit

TODAY = date(2026, 6, 10)


def _e(qid, *, next_due, last_grade="fair", mastered=False):
    return ScheduleEntry(question_id=qid, next_due=next_due, last_grade=last_grade, mastered=mastered,
                         interval_days=2)


def test_overdue_first_then_new():
    entries = {
        "overdue": _e("overdue", next_due="2026-06-05", last_grade="poor"),
        "today": _e("today", next_due="2026-06-10", last_grade="good"),
    }
    q = due_queue(entries, ["overdue", "today", "fresh"], today=TODAY, capacity=5)
    ids = [it.question_id for it in q.items]
    assert ids[0] == "overdue"            # most overdue ranks first
    assert "fresh" in ids                  # new question is due
    assert ids.index("fresh") > ids.index("overdue")  # new ranked after overdue (FR-014)


def test_capacity_caps_and_carries_forward():
    entries = {f"q{i}": _e(f"q{i}", next_due="2026-06-01") for i in range(8)}
    q = due_queue(entries, list(entries), today=TODAY, capacity=5)
    assert len(q.items) == 5
    assert q.carried_forward == 3          # no question dropped (FR-015)


def test_mastered_excluded():
    entries = {
        "m": _e("m", next_due="2026-06-01", last_grade="strong", mastered=True),
        "due": _e("due", next_due="2026-06-09"),
    }
    q = due_queue(entries, ["m", "due"], today=TODAY, capacity=5)
    assert [it.question_id for it in q.items] == ["due"]


def test_nonempty_while_any_below_mastery():
    """Nothing strictly due today, but a below-mastery question exists → surfaced (FR-013)."""
    entries = {"future": _e("future", next_due="2026-06-20", last_grade="good")}
    q = due_queue(entries, ["future"], today=TODAY, capacity=5)
    assert len(q.items) == 1
    assert q.items[0].question_id == "future"


def test_empty_only_when_all_mastered():
    entries = {"m": _e("m", next_due="2026-07-01", last_grade="strong", mastered=True)}
    q = due_queue(entries, ["m"], today=TODAY, capacity=5)
    assert q.items == []
