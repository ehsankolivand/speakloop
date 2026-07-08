"""T018 (018, US1) — card scheduling (shared SRS ladder) + due-selection."""

from __future__ import annotations

from datetime import date

import pytest

from speakloop.linecards import cards, deck

pytestmark = pytest.mark.unit

TODAY = date(2026, 7, 1)


def _row(**kw):
    r = cards.new_state()
    r.update(kw)
    return r


def test_again_reschedules_to_shortest_interval():
    st = deck.advance_card(cards.new_state(), "poor", today=TODAY)
    assert st["interval_days"] == 1
    assert st["next_due"] == "2026-07-02"
    assert st["total_reviews"] == 1


def test_again_card_is_due_on_the_next_run():
    cardsmap = {"c": deck.advance_card(cards.new_state(), "poor", today=TODAY)}
    assert deck.select_due(cardsmap, today=date(2026, 7, 2), capacity=20) == ["c"]


def test_two_easy_marks_master_and_leave_daily_rotation():
    st = deck.advance_card(cards.new_state(), "strong", today=TODAY)
    assert st["mastered"] is False and st["consecutive_strong"] == 1
    st2 = deck.advance_card(st, "strong", today=date(2026, 7, 3))
    assert st2["mastered"] is True
    assert st2["interval_days"] == 30  # maintenance ceiling
    # a mastered card 30 days out is not in the daily deck
    assert deck.select_due({"c": st2}, today=date(2026, 7, 4), capacity=20) == []


def test_due_order_is_most_overdue_first():
    cardsmap = {
        "recent": _row(next_due="2026-07-01", last_grade="good"),
        "old": _row(next_due="2026-06-20", last_grade="good"),
        "new": cards.new_state(),  # never reviewed -> due today
    }
    due = deck.select_due(cardsmap, today=TODAY, capacity=20)
    assert due[0] == "old"
    assert set(due) == {"old", "recent", "new"}


def test_capacity_truncates_the_run():
    cardsmap = {f"c{i}": cards.new_state() for i in range(5)}
    assert len(deck.select_due(cardsmap, today=TODAY, capacity=2)) == 2


def test_nothing_due_returns_empty_but_practise_ahead_offers_soonest():
    cardsmap = {"future": _row(next_due="2026-08-01", last_grade="strong")}
    assert deck.select_due(cardsmap, today=TODAY, capacity=20) == []
    assert deck.select_due(cardsmap, today=TODAY, capacity=20, ahead=True) == ["future"]


def test_any_due():
    assert deck.any_due({"new": cards.new_state()}, today=TODAY) is True
    assert deck.any_due({"f": _row(next_due="2026-08-01")}, today=TODAY) is False
