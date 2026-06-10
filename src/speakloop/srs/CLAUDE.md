# srs

## Purpose

Spaced-repetition scheduling (010-interview-loop, P2b). Pure logic — turns a
session's answer-quality grade into a per-question review schedule, decides
mastery, and computes the daily due queue. No LLM, no engine; stdlib only.

## Public interface

- `grade.grade_session(*, coverage_aggregate, content_error_count=0, grammar_patterns=None) -> Grade`
  — poor/fair/good/strong. Coverage-primary; falls back to grammar severity when
  coverage is `None` (FR-010). `grade.Grade` is the literal type.
- `schedule.next_due(entry, grade, *, today) -> ScheduleEntry` — the interval ladder
  (poor→1d, fair→2d, good→×2, strong→×2.5; cap 21d; mastery = 2 consecutive strong →
  30d maintenance; non-strong demotes a mastered question).
- `queue.due_queue(entries, all_question_ids, *, today, capacity=5) -> DueQueue` —
  priority order (most overdue → lower grade → oldest practiced; new questions after
  overdue ones); non-empty while any question is below mastery; overflow carried
  forward, never dropped. `queue.DueItem`, `queue.DueQueue`.

## Dependencies

- Internal: `speakloop.store` (`ScheduleEntry`). No LLM/engine packages.

## Consumers

`sessions` (the coordinator grades a session + advances its schedule), `cli`
(the `today` command + practice's due-question selection).

## File map

- `grade.py` — the answer-quality band.
- `schedule.py` — the interval ladder + mastery transitions.
- `queue.py` — the due-queue computation.

## Common modification patterns

- **Tune the ladder / bands**: edit the constants at the top of `schedule.py` /
  `grade.py` — the observable contract (poor→1d, success→growing, mastery→sustained
  strong) is fixed by the spec; only the numbers move.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  Key Definitions + clarifications in `specs/010-interview-loop/spec.md`.
