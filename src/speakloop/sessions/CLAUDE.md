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
  **012:** also takes an injected `key_reader` (single-key controls), `analysis_parallel_safe` +
  `analysis_concurrency` (engine-capability concurrency), `timings_display`, and `ui_sleep`.
- `keyboard.py` (012) — `KeyReader` (Protocol) + `RawKeyReader`/`NullKeyReader`/`FakeKeyReader`
  + `make_key_reader()`. The ONE raw-input module (consolidates the old `cli/practice._cbreak_read`
  + `coordinator._spawn_enter_reader`); stdlib termios/tty/select only. Canonical keys
  `space`/`enter`/`r`/`s`/`q`. Tests inject `FakeKeyReader` — no test touches a real keyboard.
- `session_ui.py` (012) — one-state-at-a-time `rich` display: `SessionState`,
  `control_hint`, `countdown` (visual `3·2·1`, injectable sleep), `make_recording_progress`
  (`● REC`), `working` (TRANSCRIBING/ANALYZING spinner), `render_summary` (closing summary).
- `analysis.py` (012) — `run_group(jobs, *, parallel_safe, concurrency)`: serial for a single
  in-process model, `ThreadPoolExecutor(cap)` for a parallel-safe engine; per-job error
  capture; results keyed by NAME so serial == concurrent assembly (byte-identical report).
- `timer.run(budget_seconds, early_exit_event)` — `rich.progress` countdown.
- `abort.install_signal_handler(sessions_dir)` — SIGINT cleanup; removes `*.tmp`; exit 130.

## Dependencies

- Internal: `speakloop.asr`, `speakloop.audio`, `speakloop.config`, `speakloop.content`,
  `speakloop.feedback`, `speakloop.metrics`. No engine packages imported here (engines arrive
  via injected wrappers).

## Consumers

`audio` (imports `abort`), `cli` (`practice` drives `run_session`).

## File map

- `coordinator.py` — the 4/3/2 state machine + report assembly hand-off. 012: `_record_stage`
  (countdown + `● REC` + key poller), `_record_attempt`/`_transcribe_attempt` (background ASR
  overlap, single worker), `_analyze` (engine-capability-aware executor; gates preserved), and
  follow-ups reordered to fire the instant the final transcript lands.
- `keyboard.py` (012) — the single raw-input `KeyReader` seam.
- `session_ui.py` (012) — one-state-at-a-time `rich` display + countdown + summary.
- `analysis.py` (012) — serial/concurrent `run_group` executor (byte-identical report).
- `timer.py` — per-attempt countdown.
- `abort.py` — SIGINT handler; cleans `*.tmp`; exits 130.

## Common modification patterns

- **Change attempt count/timing (4/3/2)**: edit `coordinator.py` + `timer.py`.
- **Adjust abort/cleanup behaviour**: edit `abort.py` only.
- **Add a single-key control**: extend `keyboard.canonicalize` + the state→keys map in
  `session_ui.control_hint`, then wire it where the stage is driven in `coordinator.py`.
- **Change analysis concurrency**: it is engine-declared (`engine.parallel_safe`) + capped by
  `loop.yaml analysis_concurrency`; the executor lives in `analysis.py`. Keep jobs PURE
  (no store mutation inside a job) so the serial/concurrent reports stay byte-identical.

## Never do

- Import an engine package here — engines are injected as wrappers (Principle V).
- Mutate the store inside an analysis job (breaks the byte-identical guarantee) — apply store
  writes on the main thread after `run_group` returns (012).
- Run two transcription jobs at once — the ASR worker pool is `max_workers=1` (FR-022).
- Let an automated test touch a real keyboard/mic — inject `FakeKeyReader` + a fake `record_fn`.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md); methodology: `doc/research_methodology.md`.
