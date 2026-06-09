# sessions

## Purpose

Orchestrator for the 4/3/2 practice loop — drives the per-question state machine, runs the
per-attempt timer, and handles clean abort. This is the coordinator that ties asr, audio,
content, feedback, and metrics together for one session.

## Public interface

- `coordinator.run_session(...)` — state machine
  `listening → attempt_1..3 → analyzing → reporting → done`. Takes injected `grammar_analyzer`
  and (009) an optional `coach` callable: the coach runs ONLY after a SUCCESSFUL grammar
  analysis (cloud only; `None` in local mode), sets `session.coaching`, and degrades gracefully
  to a non-fatal `coach_error` on any failure — never blocking the grammar report.
- `timer.run(budget_seconds, early_exit_event)` — `rich.progress` countdown.
- `abort.install_signal_handler(sessions_dir)` — SIGINT cleanup; removes `*.tmp`; exit 130.

## Dependencies

- Internal: `speakloop.asr`, `speakloop.audio`, `speakloop.config`, `speakloop.content`,
  `speakloop.feedback`, `speakloop.metrics`. No engine packages imported here (engines arrive
  via injected wrappers).

## Consumers

`audio` (imports `abort`), `cli` (`practice` drives `run_session`).

## File map

- `coordinator.py` — the 4/3/2 state machine + report assembly hand-off.
- `timer.py` — per-attempt countdown.
- `abort.py` — SIGINT handler; cleans `*.tmp`; exits 130.

## Common modification patterns

- **Change attempt count/timing (4/3/2)**: edit `coordinator.py` + `timer.py`.
- **Adjust abort/cleanup behaviour**: edit `abort.py` only.

## Never do

- Import an engine package here — engines are injected as wrappers (Principle V).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md); methodology: `doc/research_methodology.md`.
