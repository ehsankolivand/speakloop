"""Spaced-repetition interval ladder + mastery (010-interview-loop, P2b).

A lightweight, grade-banded multiplicative ladder (research R1) — no per-card ease
factor. The next interval is a pure function of (previous interval, grade), exactly
as pinned in the spec Key Definitions / clarifications:

    poor  → 1 day (reset to base)     good   → previous × 2
    fair  → 2 days                    strong → previous × 2.5

Intervals are capped at 21 days until mastered. Mastery = two consecutive `strong`
grades (which, by the grade bands, already imply zero content errors); a mastered
question leaves the active queue and returns once at the 30-day maintenance ceiling,
and any later non-`strong` result demotes it back into rotation.

Pure logic — no LLM/engine. Operates on ``store.model.ScheduleEntry``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from speakloop.srs.grade import Grade
from speakloop.store.model import ScheduleEntry

BASE_INTERVAL_DAYS = 1
FAIR_INTERVAL_DAYS = 2
GOOD_MULTIPLIER = 2.0
STRONG_MULTIPLIER = 2.5
CAP_DAYS = 21
MAINTENANCE_DAYS = 30
MASTERY_STREAK = 2


@dataclass(frozen=True)
class AdvanceResult:
    """The three ladder outputs of one review, independent of what is being scheduled
    (a question or a rescue-line card). Dates are stamped by the caller."""

    interval_days: int
    consecutive_strong: int
    mastered: bool


def advance(
    prev_interval: int, consecutive_strong: int, mastered: bool, grade: Grade
) -> AdvanceResult:
    """The pure interval-ladder recurrence (018): given the previous interval + streak +
    mastery and a review grade, return the next interval, streak, and mastery.

    This is the SINGLE ladder used by both ``next_due`` (per-question schedule) and
    ``linecards`` (per-card schedule) so the constants above stay the one tuning surface
    (owner O14). Behaviour is byte-identical to the pre-018 ``next_due`` body.
    """
    prev = prev_interval if prev_interval and prev_interval >= 1 else BASE_INTERVAL_DAYS
    consecutive = consecutive_strong

    # A non-strong result on a mastered item demotes it: drop back to the base ladder
    # and re-enter rotation (Key Definitions).
    if grade != "strong" and mastered:
        mastered = False
        prev = BASE_INTERVAL_DAYS

    if grade == "poor":
        interval = BASE_INTERVAL_DAYS
        consecutive = 0
    elif grade == "fair":
        interval = FAIR_INTERVAL_DAYS
        consecutive = 0
    elif grade == "good":
        interval = min(int(prev * GOOD_MULTIPLIER), CAP_DAYS)
        consecutive = 0
    else:  # strong
        consecutive += 1
        interval = min(int(round(prev * STRONG_MULTIPLIER)), CAP_DAYS)
        if consecutive >= MASTERY_STREAK:
            mastered = True
            interval = MAINTENANCE_DAYS

    return AdvanceResult(interval_days=interval, consecutive_strong=consecutive, mastered=mastered)


def next_due(entry: ScheduleEntry, grade: Grade, *, today: date) -> ScheduleEntry:
    """Return a NEW ScheduleEntry advanced by one review graded ``grade``."""
    result = advance(entry.interval_days, entry.consecutive_strong, entry.mastered, grade)
    return ScheduleEntry(
        question_id=entry.question_id,
        last_grade=grade,
        interval_days=result.interval_days,
        next_due=(today + timedelta(days=result.interval_days)).isoformat(),
        consecutive_strong=result.consecutive_strong,
        mastered=result.mastered,
        last_practiced=today.isoformat(),
        total_reviews=entry.total_reviews + 1,
    )
