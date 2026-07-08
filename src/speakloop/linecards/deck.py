"""Deck scheduling + due-selection for rescue-line cards (018, US1).

Reuses the shared SRS ladder (`srs.schedule.advance`) so cards and questions share the one
tuning surface. Pure logic — operates on the `card_id -> {content + SRS state}` map produced by
`cards.merge_cards`. No engine, no I/O.
"""

from __future__ import annotations

from datetime import date, timedelta

from speakloop.srs import schedule
from speakloop.srs.grade import Grade

# Grade priority for ordering due cards (lower = more urgent). A never-reviewed card ranks
# after overdue poor/fair but before strong — mirrors srs.queue._NEW_GRADE_RANK.
_GRADE_RANK: dict[str, float] = {"poor": 0.0, "fair": 1.0, "good": 2.0, "strong": 3.0}
_NEW_GRADE_RANK = 2.5


def advance_card(state: dict, grade: Grade, *, today: date) -> dict:
    """Return a NEW card-state dict advanced by one self-marked review (FR-015).

    Delegates the interval/streak/mastery to the shared `schedule.advance` ladder, then stamps
    the dates and increments the review count."""
    result = schedule.advance(
        int(state.get("interval_days") or 0),
        int(state.get("consecutive_strong") or 0),
        bool(state.get("mastered")),
        grade,
    )
    new = dict(state)
    new["last_grade"] = grade
    new["interval_days"] = result.interval_days
    new["next_due"] = (today + timedelta(days=result.interval_days)).isoformat()
    new["consecutive_strong"] = result.consecutive_strong
    new["mastered"] = result.mastered
    new["last_practiced"] = today.isoformat()
    new["total_reviews"] = int(state.get("total_reviews") or 0) + 1
    return new


def _is_due(row: dict, today_iso: str) -> bool:
    nd = row.get("next_due")
    return not nd or str(nd) <= today_iso


def _sort_key(item: tuple[str, dict], today_iso: str) -> tuple[str, float, str, str]:
    cid, row = item
    nd = str(row.get("next_due") or today_iso)  # a never-reviewed card sorts as due today
    grade = row.get("last_grade")
    rank = _GRADE_RANK.get(str(grade), _NEW_GRADE_RANK) if grade else _NEW_GRADE_RANK
    last = str(row.get("last_practiced") or "")  # oldest-practiced first ("" = never → first)
    return (nd, rank, last, cid)


def select_due(
    cards: dict[str, dict], *, today: date, capacity: int, ahead: bool = False
) -> list[str]:
    """Return due card ids in review-priority order (most overdue first, ties by lower grade
    then oldest practiced), truncated to ``capacity`` (FR-016).

    A card is due when it has never been reviewed or its ``next_due`` is today-or-earlier. When
    nothing is due and ``ahead`` is set, return the soonest-due cards instead (practise-ahead,
    FR-020)."""
    today_iso = today.isoformat()
    ordered = sorted(cards.items(), key=lambda it: _sort_key(it, today_iso))
    due = [cid for cid, row in ordered if _is_due(row, today_iso)]
    if not due and ahead:
        due = [cid for cid, _row in ordered]
    cap = max(1, int(capacity))
    return due[:cap]


def any_due(cards: dict[str, dict], *, today: date) -> bool:
    """Whether at least one card is due today (drives the 'caught up' message, FR-020)."""
    today_iso = today.isoformat()
    return any(_is_due(row, today_iso) for row in cards.values())
