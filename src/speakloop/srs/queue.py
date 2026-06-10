"""Due-queue computation (010-interview-loop, P2b).

Builds the "what should I practice today" queue from the SRS schedule + the full
question list. Priority order (Key Definitions): most overdue first, ties broken by
lower last grade, then oldest last-practiced. New (no-history) questions are due but
ranked AFTER overdue below-mastery questions so a first run does not bury reviews
(FR-014). The queue is non-empty whenever any question is below mastery (FR-013):
when nothing is strictly due today but below-mastery questions exist, the
soonest-due ones are surfaced anyway. Overflow beyond the daily capacity is carried
forward, never dropped (FR-015).

Pure logic — no LLM/engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from speakloop.store.model import ScheduleEntry

_GRADE_RANK = {"poor": 0, "fair": 1, "good": 2, "strong": 3}
_NEW_GRADE_RANK = 2.5  # new questions rank after overdue weak ones, before strong


@dataclass(frozen=True)
class DueItem:
    question_id: str
    next_due: str | None
    last_grade: str | None
    days_overdue: int
    is_new: bool


@dataclass(frozen=True)
class DueQueue:
    items: list[DueItem]  # the capacity-sized subset to practice today
    carried_forward: int  # how many due items did not fit today's capacity


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _sort_key(item: DueItem):
    grade_rank = _NEW_GRADE_RANK if item.is_new else _GRADE_RANK.get(item.last_grade or "", 2)
    # most overdue first (negate), then lower grade, then oldest last-practiced.
    last = _parse_date(item.next_due) or date.min
    return (-item.days_overdue, grade_rank, last.toordinal())


def due_queue(
    entries: dict[str, ScheduleEntry],
    all_question_ids: list[str],
    *,
    today: date,
    capacity: int = 5,
) -> DueQueue:
    """Compute today's due queue in priority order, capped at ``capacity``."""
    below_mastery: list[DueItem] = []
    for qid in all_question_ids:
        entry = entries.get(qid)
        if entry is None:
            below_mastery.append(
                DueItem(question_id=qid, next_due=today.isoformat(), last_grade=None,
                        days_overdue=0, is_new=True)
            )
            continue
        if entry.mastered:
            continue  # mastered → excluded from the active queue (FR-013a)
        nd = _parse_date(entry.next_due)
        overdue = max(0, (today - nd).days) if nd else 0
        below_mastery.append(
            DueItem(question_id=qid, next_due=entry.next_due, last_grade=entry.last_grade,
                    days_overdue=overdue, is_new=False)
        )

    if not below_mastery:
        return DueQueue(items=[], carried_forward=0)  # everything mastered

    # Strictly due today (arrived next_due, or a brand-new question).
    due_now = [
        it for it in below_mastery
        if it.is_new or (_parse_date(it.next_due) is not None and _parse_date(it.next_due) <= today)
    ]
    # FR-013: never empty while anything is below mastery — if nothing is strictly
    # due, surface the soonest-due below-mastery questions instead.
    candidates = due_now if due_now else sorted(
        below_mastery, key=lambda it: _parse_date(it.next_due) or date.max
    )

    ordered = sorted(candidates, key=_sort_key)
    today_items = ordered[: max(1, capacity)]
    carried = max(0, len(ordered) - len(today_items))
    return DueQueue(items=today_items, carried_forward=carried)
