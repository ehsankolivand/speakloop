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


def next_due(entry: ScheduleEntry, grade: Grade, *, today: date) -> ScheduleEntry:
    """Return a NEW ScheduleEntry advanced by one review graded ``grade``."""
    prev = entry.interval_days if entry.interval_days and entry.interval_days >= 1 else BASE_INTERVAL_DAYS
    consecutive = entry.consecutive_strong
    mastered = entry.mastered

    # A non-strong result on a mastered question demotes it: drop back to the base
    # ladder and re-enter rotation (Key Definitions).
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

    return ScheduleEntry(
        question_id=entry.question_id,
        last_grade=grade,
        interval_days=interval,
        next_due=(today + timedelta(days=interval)).isoformat(),
        consecutive_strong=consecutive,
        mastered=mastered,
        last_practiced=today.isoformat(),
        total_reviews=entry.total_reviews + 1,
    )
