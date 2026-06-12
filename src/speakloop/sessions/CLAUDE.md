# sessions

## Purpose

Orchestrates the 4/3/2 practice loop — per-question state machine, attempt timer,
single-key controls, background ASR worker, concurrent analysis executor, and clean abort.

## Public interface

- `coordinator.run_session(question, *, tts_engine, play_fn, asr_engine, record_fn,
  grammar_analyzer, coach, runners, listen_in_session, store_path, console, sessions_dir,
  scratch_dir, now, asr_engine_name, asr_model_id, asr_fell_back, analysis_parallel_safe,
  analysis_concurrency, timings_display, key_reader, ui_sleep) -> SessionResult`
  — full 4/3/2 state machine. Returns `SessionResult(report_path, session)`.
  Coach runs only after a successful grammar pass; degrades gracefully to `coach_error`.
  Follow-up generation fires BEFORE heavy analysis the instant the final transcript lands
  (`coordinator.py:1048-1069`).
- `coordinator.PronunciationDrills` (016) — injected bundle (`scorer`, `bank`, `engine_note`),
  built by `cli/practice.py` ONLY after the safety gate permitted + the user opted in. When
  passed, `run_session` runs `_analyze` in a BACKGROUND daemon thread (`quiet=True`, to a
  discard console — two live `rich` displays must never collide) while `_run_pronunciation_drills`
  runs the user-paced read-aloud drill block on the main thread, then JOINs → one report waits
  for both (FR-002/003/004). No-op (None) when absent → byte-identical; drill WAVs are scratch,
  discarded after scoring. `_analyze(..., quiet=…)` swaps the spinner for a no-op context.
- `coordinator.Runners` — dataclass of optional LLM callables injected by `cli/practice.py`
  (`coordinator.py:40-62`): `mishearing`, `followups`, `consistency`, `drill`, `keypoints`,
  `coverage`. Each is `Callable | None`; absent capability → feature skipped, session runs.
- `coordinator.SessionResult` — `NamedTuple(report_path, session)` (`coordinator.py:68-78`).
- `coordinator.FOLLOWUP_BUDGET_SECONDS = 60`, `coordinator.WARMUP_ITEM_BUDGET_SECONDS = 20`
  (`coordinator.py:36,538`).
- `keyboard.KeyReader` (Protocol) + `RawKeyReader` / `NullKeyReader` / `FakeKeyReader` +
  `make_key_reader()` (`keyboard.py:49-226`). The session-path key reader — stdlib
  termios/tty/select only.
  Key surface by stage:
  - Pre-session listen loop (driven by `cli/practice.py`, NOT this module): `space`/`enter`=skip,
    `r`=replay, `q`=quit. `cli/practice.py:118` and `debrief/menu.py:34` keep their own cbreak
    readers; see root CLAUDE.md Trap 6.
  - Recording stage (`_spawn_key_poller`): `space`/`enter`=stop recording early; `s`=skip
    follow-up (follow-up case only). `q` is NOT wired inside the recording loop.
  `RawKeyReader` has a re-entrancy depth guard (`keyboard.py:88`) so a shared reader
  re-entered by nested `with` blocks does not double-save terminal state.
  `FakeKeyReader` has two modes: scripted list of keys per poll; or time-gated schedule
  with an injected clock (`keyboard.py:168-210`).
- `session_ui.SessionState`, `control_hint`, `countdown`, `make_recording_progress` (`● REC`),
  `working`, `render_summary` — one-state-at-a-time `rich` display (012, US1). Every
  blocking LLM/ASR wait in the coordinator runs under a labeled `working` state —
  warm-up drill (`_run_warmup`), follow-up generation (`_run_follow_ups`), analysis
  (`_analyze`), and the transcribe wait — so the terminal never sits silent (FR-002).
- `analysis.run_group(jobs, *, parallel_safe, concurrency) -> dict[str, JobResult]` — serial
  when `not parallel_safe` OR `concurrency <= 1` OR `len(jobs) <= 1`; otherwise
  `ThreadPoolExecutor(min(concurrency, len(jobs)))`. Results keyed by NAME (never completion
  order) so assembly is identical regardless of strategy (`analysis.py:48-73`).
- `timer.run(budget_seconds, early_exit_event)` — `rich.progress` countdown.
- `abort.install_signal_handler(sessions_dir)` — SIGINT handler: removes `*.tmp` under
  `sessions_dir` and sets `abort_event` (`abort.py:26-37`). There is NO `sys.exit(130)` in
  the handler; the coordinator polls `abort_event` and raises `AbortedError`, which
  `cli/practice.py` catches (one yellow line, `typer.Exit(130)`, FR-016). An abort during
  the follow-up stage does NOT raise — the coordinator still writes a resumable
  analysis-pending report (`coordinator.py:457`, `:1077`).

## O6 — serial == concurrent byte-identical report (owner)

Analysis jobs in `analysis.run_group` are PURE — they read shared state but MUST NOT mutate
it. Store writes happen on the main thread after the group returns, in a fixed order
(`coordinator.py:1110-1116`). Results assembled from name-keyed slots in fixed insertion
order. `timings` frontmatter is non-deterministic (wall-clock) and stripped before any
byte comparison. Concurrency is engine-declared via per-class `parallel_safe` attribute
(`qwen_engine.py:47` False, `openrouter_engine.py:41` True, `claude_code_engine.py:183` True)
— local Qwen always runs serial.
Gate: `tests/integration/test_analysis_equivalence.py`.
016 preserves O6: running `_analyze` in a background thread (drill-concurrent path) does not
change its output (same name-keyed slots, same fixed-order assembly); the drill block never
touches the store, and the single store mutation stays on the main thread after the join — so
a no-drills report is byte-identical (gate: `test_drills_additive_byte_identical.py`).

## Dependencies

- Internal: `speakloop.asr`, `speakloop.audio`, `speakloop.config`, `speakloop.content`,
  `speakloop.coverage`, `speakloop.feedback`, `speakloop.metrics`, `speakloop.srs`,
  `speakloop.store`, `speakloop.trends`, `speakloop.triage`, `speakloop.warmup`,
  `speakloop.pronunciation` (016 — only `feedback.live_flag_summary`, function-local; the
  scorer is injected, never imported here, so the coordinator loads no torch/transformers).
  Most are conditional/function-local in `coordinator.py`.
- No engine packages imported here — engines arrive as injected wrappers (Principle V).

## Consumers

`audio` (lazy-imports `abort` in `recorder.py:44` to avoid circular load), `cli`.

## File map

- `coordinator.py` — 4/3/2 state machine + report assembly. `_BackgroundAsr`
  (`coordinator.py:239-285`): a single queue-fed daemon thread (NOT a ThreadPoolExecutor);
  one Whisper job at a time; daemon so a crash cannot hang exit. `Runners` + `SessionResult`
  at `:40-78`. Follow-up reorder at `:1048-1069`. Store write at `:1110-1116`.
- `keyboard.py` — `KeyReader` seam; re-entrancy guard at `:88`; `FakeKeyReader` two modes.
- `session_ui.py` — one-state-at-a-time display + countdown + closing summary.
- `analysis.py` — serial/concurrent `run_group`; serial fallback logic at `:62`.
- `timer.py` — per-attempt countdown.
- `abort.py` — SIGINT handler; sets `abort_event`; cleans `*.tmp`.

## Invariants & traps

- Jobs passed to `run_group` MUST be pure — no store mutation inside a job. Violation breaks
  the byte-identical guarantee (O6 above).
- Never run two transcription jobs at once — `_BackgroundAsr` enforces one Whisper job at a
  time by design.
- Never import an engine package here — engines are injected wrappers.
- Never let an automated test touch a real keyboard/mic — inject `FakeKeyReader` + fake
  `record_fn`. See `.claude/rules/testing.md`.

## Common modification patterns

- **Change attempt count/timing**: edit `coordinator.py` + `timer.py`.
- **Add a single-key control in the recording stage**: extend `keyboard.canonicalize` +
  `session_ui.control_hint`, wire the key in `_spawn_key_poller` in `coordinator.py`.
- **Change analysis concurrency**: `engine.parallel_safe` + `loop.yaml analysis_concurrency`;
  executor lives in `analysis.py`. Keep jobs pure (O6).
- **Adjust abort/cleanup**: edit `abort.py` only.

## Pointers

- Root map: `../../../CLAUDE.md` (engine-import rule O1, torchaudio O2, schema_version O3,
  keyboard consolidation Trap 6).
- Concurrency contract: `specs/012-responsive-session-flow/contracts/analysis-concurrency.md`.
- Testing rules: `.claude/rules/testing.md`.
