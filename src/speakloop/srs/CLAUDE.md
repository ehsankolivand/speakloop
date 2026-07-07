# srs

## Purpose

Spaced-repetition scheduling (010-interview-loop, P2b). Pure logic — converts a
session's answer-quality grade into a per-question review schedule, decides mastery,
and builds the daily due queue. No LLM, no engine; stdlib only.

## Public interface

- `grade.grade_session(*, coverage_aggregate, content_error_count=0, grammar_patterns=None) -> Grade`
  — `Grade = Literal["poor","fair","good","strong"]`. Coverage-primary.
  Grammar-fallback thresholds when `coverage_aggregate is None` (grade.py:62-68):
  0 occurrences → strong; ≤2 → good; ≤3–5 → fair; >5 → poor.
- `schedule.next_due(entry, grade, *, today) -> ScheduleEntry` — interval ladder
  (schedule.py:25-31): poor→1d, fair→2d, good→prev×2, strong→prev×2.5; cap 21d;
  mastery = 2 consecutive strong → 30d maintenance; any non-strong demotes mastered.
  Interval-ladder constants (BASE_INTERVAL_DAYS, FAIR_INTERVAL_DAYS, GOOD_MULTIPLIER,
  STRONG_MULTIPLIER, CAP_DAYS, MAINTENANCE_DAYS, MASTERY_STREAK) are the single tuning
  surface — owned at the top of schedule.py (owner O14).
- `queue.due_queue(entries, all_question_ids, *, today, capacity=5) -> DueQueue`
  — priority order: most overdue first, ties by lower grade, then oldest practiced.
  New questions use `_NEW_GRADE_RANK=2.5` (queue.py:23) — rank after overdue
  poor/fair but before strong-overdue. The tertiary tiebreak is `DueItem.last_practiced`
  (oldest first; `None`→`date.min`) — populated from `entry.last_practiced` — so equally-
  overdue same-grade questions no longer collapse to question-file order (IMP-008/FR-014).
  Capacity floored at 1 (`max(1, capacity)`,
  queue.py:102). Non-empty while any question is below mastery; overflow carried
  forward, never dropped.

## Dependencies & consumers

- Depends on: `speakloop.store` (`ScheduleEntry`). No engine packages.
- Consumers: `sessions/coordinator.py` (grades session + advances schedule after
  each report); `cli/resume.py:147,183` (grades resumed sessions + advances
  schedule); `cli/today.py` (due-queue selection for daily loop).

## File map

- `grade.py` — Grade type + `grade_session`; grammar-fallback thresholds lines 62-68.
- `schedule.py` — interval-ladder constants (lines 25-31) + `next_due`; owns O14.
- `queue.py` — `_NEW_GRADE_RANK` (line 23), `due_queue`, `DueItem`, `DueQueue`.

## Invariants & traps

- Pure functions — no I/O, no mutation of passed-in objects.
- `next_due` returns a NEW `ScheduleEntry`; never mutates the input.
- The interval ladder constants in schedule.py are the spec-pinned contract; only
  numbers move, not the shape (poor→reset, success→growing, mastery→sustained strong).

## Common modification patterns

- **Tune ladder or grade bands**: change constants at top of schedule.py / grade.py.
- **Add a new grade level**: update the Grade literal, grade_session, _GRADE_RANK in
  queue.py, and the ladder branch in next_due.

## Pointers

- Root map: `../../../CLAUDE.md`.
- Key Definitions: `specs/010-interview-loop/spec.md`.
- schema_version rule: root CLAUDE.md (owner O3).
