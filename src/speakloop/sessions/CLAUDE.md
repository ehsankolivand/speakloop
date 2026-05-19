# sessions

Orchestrator for the 4/3/2 practice loop.

**Public surface**:

- `coordinator.run_session(...)` — state machine `listening → attempt_1..3 → analyzing → reporting → done`.
- `timer.run(budget_seconds, early_exit_event)` — `rich.progress` countdown.
- `abort.install_signal_handler(sessions_dir)` — SIGINT cleanup; removes `*.tmp`; exit 130.
