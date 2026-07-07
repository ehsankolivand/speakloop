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
- `coordinator.PronunciationDrills` (016, +017) — injected bundle (`scorer`, `bank`, `engine_note`,
  `tts_playback`, `retries`, `teach_speed`), built by `cli/practice.py` ONLY after the safety gate
  permitted + the user opted in. `teach_speed` (P2) is the slower per-call rate for the focused
  teaching beat; `_run_pronunciation_drills` builds a `teach_speak` closure (`synthesize(speed=…)`,
  falling back when the engine has no per-call speed) and passes it to `run_drill_block`. When passed, `run_session` runs `_analyze` in a BACKGROUND daemon thread
  (`quiet=True`, to a discard console — two live `rich` displays must never collide) while
  `_run_pronunciation_drills` runs the user-paced read-aloud drill block on the main thread, then
  JOINs → one report waits for both (FR-002/003/004). No-op (None) when absent → byte-identical;
  drill WAVs are scratch, discarded after scoring. `_analyze(..., quiet=…)` swaps the spinner for a
  no-op context.
  - **017 (hear → say → see → retry)**: the per-drill loop is the pure `pronunciation.run_drill_item`
    (hear-first via the injected TTS, replay-on-demand with `r`, bounded automatic retry on a flagged
    item). `_run_pronunciation_drills` only builds the `speak` closure (`tts_engine.synthesize` +
    `play_fn`, no-op when either is None → 016 behaviour) and the `record` closure (`_record_stage`),
    applies `pronunciation.select_drills` weak-sound ordering (`_weak_contrasts_from_store(store)`),
    keeps the 016 bounded follow-on routing, and assembles via `pronunciation.build_block_result`.
    `DrillQuit` (learner pressed `q`) + `abort_event` both stop asking for more. Retry/tricky-sounds
    data is additive (data-model §2/§3) → a no-drills / non-interactive run stays byte-identical.
- `coordinator.Runners` — dataclass of optional LLM callables injected by `cli/practice.py`
  (`coordinator.py:40-62`): `mishearing`, `followups`, `consistency`, `drill`, `keypoints`,
  `coverage`. Each is `Callable | None`; absent capability → feature skipped, session runs.
- `coordinator.SessionResult` — `NamedTuple(report_path, session)` (`coordinator.py:68-78`).
- `coordinator.FOLLOWUP_BUDGET_SECONDS = 60`, `coordinator.WARMUP_ITEM_BUDGET_SECONDS = 20`
  (`coordinator.py:36,538`).
- `keyboard.KeyReader` (Protocol) + `RawKeyReader` / `NullKeyReader` / `FakeKeyReader` +
  `make_key_reader()`. The session-path key reader — stdlib termios/tty/select only.
- `keyboard.read_key_blocking(*, decode, line_parse, read_bytes=1, eof_value)` (IMP-016) — the
  shared BLOCKING single-key reader for the listen loop + debrief menu (distinct from the
  session-path `KeyReader`): stdin-then-`/dev/tty` cbreak read → caller's `decode(bytes)`, else
  line-buffered `input()` → caller's `line_parse(str)`, `eof_value` on EOF.
  Key surface by stage:
  - Pre-session listen loop (driven by `cli/practice.py`, NOT this module): `space`/`enter`=skip,
    `r`=replay, `q`=quit. `cli/practice._read_key` and `debrief/menu.read_key` now share the
    blocking `keyboard.read_key_blocking(*, decode, line_parse, read_bytes, eof_value)` (IMP-016);
    see root CLAUDE.md Trap 6.
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
  `sessions_dir` and sets `abort_event`. There is NO `sys.exit(130)` in
  the handler; the coordinator polls `abort_event` and raises `AbortedError`, which
  `cli/practice.py` catches (one yellow line, `typer.Exit(130)`, FR-016). An abort during
  the follow-up stage does NOT raise — the coordinator still writes a resumable
  analysis-pending report (`coordinator.py:457`, `:1077`). `install_signal_handler` RETURNS
  the prior SIGINT handler and `run_session` wraps its whole body in `try/finally` to call
  `abort.restore_signal_handler(prev)` on every exit — otherwise the inert handler (it never
  raises) stays live and silently swallows every later Ctrl-C in the process (IMP-001).

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

- `coordinator.py` — 4/3/2 state machine + report assembly. `_BackgroundAsr`: a single
  queue-fed daemon thread (NOT a ThreadPoolExecutor); one Whisper job at a time; daemon so a
  crash cannot hang exit. `Runners` + `SessionResult` near the top. `run_session` orchestrates
  named phase helpers (IMP-003): `_record_and_transcribe` (attempt loop + `_BackgroundAsr` +
  abort cleanup → transcripts), `_run_analysis_phase` (the three analysis strategies incl. the
  drills-concurrent background thread → `(outs, drills_result)`; an UNEXPECTED background crash
  still degrades to a resumable pending report but surfaces the reason — one yellow line +
  threaded into `phase_c_error`, never dropped, IMP-010), and `_persist_store` (SRS
  advance + contrast tally + atomic save → next_due). All store mutations stay on the main
  thread (O6). The Session-constructor assembly + report write stay inline in `run_session`.
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
