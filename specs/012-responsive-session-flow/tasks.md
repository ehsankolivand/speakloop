# Tasks: Responsive, Transparent & Faster Practice Session

**Feature**: `012-responsive-session-flow` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Tests**: requested (fake-keyboard control paths, serial-vs-concurrent equivalence, cache
prune/invalidation, degradation). NO test touches the real `claude` binary, microphone, or
keyboard (SC-008) — all seams are injectable and faked.

**Conventions**: `[P]` = parallelizable (different file, no incomplete dep). `[USx]` maps to a
spec user story. Foundational/Setup/Polish tasks carry no story label.

---

## Phase 1: Setup

- [x] T001 Confirm baseline green (`uv run pytest -q`) and record the count in the commit body;
  create empty test modules `tests/unit/test_keyboard.py`, `tests/unit/test_timings.py`,
  `tests/unit/test_cache_prune.py`, `tests/unit/test_session_ui.py`,
  `tests/integration/test_analysis_equivalence.py` as placeholders for the phases below.

---

## Phase 2: Foundational (blocking prerequisites — no story-specific behavior yet)

- [x] T002 [P] Add `StageTimer` in `src/speakloop/feedback/timings.py`: ordered `(name, seconds,
  overlapped)` records, injectable `clock=time.perf_counter`, `stage(name, overlapped=False)`
  context manager, manual `start/stop` for overlapped stages, `to_frontmatter() -> dict` (the
  `timings` block per contracts/loop-config-and-timings.md), `render() -> rich.Table`.
- [x] T003 [P] Unit-test `StageTimer` in `tests/unit/test_timings.py` with a fake clock:
  ordering, overlapped flag, `to_frontmatter` shape, zero-duration cache-hit case.
- [x] T004 [P] Add `Session.timings: dict | None` (additive optional) in
  `src/speakloop/feedback/frontmatter.py`; emit in `dump` only when present; parse in `parse`
  (dict-guarded); confirm `schema_version` stays 1.
- [x] T005 [P] Round-trip test for `timings` in `tests/unit/` (existing frontmatter test file):
  dump→parse→dump idempotent; a no-timings session is byte-identical to today (SC-009).
- [x] T006 [P] Implement `src/speakloop/sessions/keyboard.py`: `KeyReader` protocol +
  `RawKeyReader` (termios/tty cbreak on stdin-or-`/dev/tty`, `select` poll, drain-on-enter,
  restore-on-exit), `NullKeyReader` (poll→None, `raw_capable=False`), `FakeKeyReader` (scripted
  `[(delay,key)]` with injected clock). Canonical keys per contracts/keyboard-and-states.md.
- [x] T007 [P] Unit-test `keyboard.py` in `tests/unit/test_keyboard.py`: canonicalization
  (space/enter/r/s/q, Ctrl-C→q, unknown→None), `FakeKeyReader` timing, `NullKeyReader` always
  None. No real fd opened.
- [x] T008 [P] Add `prune(max_bytes)` to `src/speakloop/tts/cache.py`: LRU-by-mtime delete until
  under cap; never delete the just-stored entry; tolerate a concurrent reader. Add a
  `TTS_CACHE_MAX_BYTES` constant (config). Call `prune` at the end of `KokoroEngine.synthesize`.
- [x] T009 [P] Tests for cache invalidation + prune in `tests/unit/test_cache_prune.py`: text
  change → new key (invalidation); prune evicts oldest, keeps newest/just-stored, respects cap.
- [x] T010 [P] Add `play_interruptible(wav_path, *, should_stop, on_first_frame=None, _player=…)`
  + `warm_output_device()` to `src/speakloop/audio/playback.py`. Extract a `_Player` seam
  (default sounddevice-backed) so the poll/stop control loop is testable without real audio;
  reuse the existing device-loss/resample recovery; keep blocking `play()` for the debrief.
- [x] T011 [P] Test `play_interruptible` control loop in `tests/unit/` with a fake `_Player`:
  stops within one poll when `should_stop` flips true; returns `interrupted` bool; runs to end
  when never stopped. No real audio device.
- [x] T012 [P] Add `parallel_safe` class attribute: `True` on `OpenRouterEngine`
  (`llm/openrouter_engine.py`) and `ClaudeCodeEngine` (`llm/claude_code_engine.py`), `False` on
  `QwenEngine` (`llm/qwen_engine.py`); test the three values.
- [x] T013 [P] Add `autoplay_ideal_answer: bool = True` and `analysis_concurrency: int = 3`
  to `LoopConfig` in `src/speakloop/config/loop_config.py` with defensive `load()` parsing
  (bool fallback; `max(1,int)`); test absent/invalid → defaults.
- [x] T014 Plumb `--timings` (default False) onto `practice` and `resume` in
  `src/speakloop/cli/main.py`; thread through `practice.run(...)` / `resume.run(...)` →
  `coordinator.run_session(... timings_display=...)`. Display-only; instrumentation always-on.

**Checkpoint**: foundational seams exist + unit-tested; nothing wired into the live session yet.

---

## Phase 3: User Story 1 — Always know the state, control it with one key (P1) 🎯 MVP

**Goal**: one unambiguous state at all times + single-key skip/replay/early-stop/skip-followup +
countdown + recording indicator. **Independent test**: drive a full session with `FakeKeyReader`
+ fake audio/clock; assert states, controls, countdown, indicator presence (no real I/O).

- [x] T015 [P] [US1] Implement `src/speakloop/sessions/session_ui.py`: `SessionState` enum +
  one-transient-region renderers (PLAYING / RECORDING `● REC`+timer+bar / TRANSCRIBING /
  ANALYZING), `countdown()` (visual `3 · 2 · 1`, ~0.5s/tick via injected clock/console),
  state→keys control-hint (FR-010). Render to an injected `rich.Console`.
- [x] T016 [P] [US1] Unit-test `session_ui.py` in `tests/unit/test_session_ui.py` with
  `Console(file=StringIO)` + fake clock: exactly-one-state, hint matches the active state's key
  map, countdown emits ticks, `● REC` present.
- [x] T017 [US1] Rewire the listen loop in `src/speakloop/cli/practice.py` to use
  `play_interruptible` + `KeyReader`: `space`=skip clip, `r`=replay, during PLAYING; consolidate
  `_cbreak_read`/`_parse_line_command` into `keyboard.py` (import from there); preserve the idle
  listen-loop commands (FR-009).
- [x] T018 [US1] Rewire `_do_attempt` in `src/speakloop/sessions/coordinator.py` to: show a
  `countdown()` then the `RECORDING` region (indicator 100% of recording, FR-003/004), and wire
  `space`/`Enter` early-stop through `KeyReader` (replacing `_spawn_enter_reader`).
- [x] T019 [US1] Wire `s`=skip-whole-follow-up + countdown + RECORDING indicator into
  `_run_follow_ups` (coordinator); skipping abandons the follow-up with no recorded answer
  (FR-008). Apply the same countdown+indicator to `_run_warmup` recordings.
- [x] T020 [US1] Replace the ad-hoc `_analyzing`/`Progress` spinners with the `session_ui`
  ANALYZING/TRANSCRIBING states so every >2s op shows a labeled state (FR-002, SC-007).
- [x] T021 [US1] Fake-keyboard control-path tests in `tests/unit/` (or
  `tests/integration/test_session_controls.py`): skip stops playback (≤ poll), replay restarts,
  early-stop ends recording→TRANSCRIBING, skip-followup advances. Use `FakeKeyReader` +
  fake `record_fn`/`play_fn`/`tts_engine`.
- [x] T022 [US1] Edge-case tests: key during a non-skippable stage ignored (FR-011); skip at the
  exact end of playback is a no-op (no double-advance); near-empty early-stopped recording uses
  existing short-answer handling; `NullKeyReader` fallback completes the session (FR-012).

**Checkpoint**: US1 independently testable & demoable; session is legible and controllable with
zero speed change.

---

## Phase 4: User Story 2 — Never forced to re-listen; closing summary (P1)

**Goal**: skippable ideal answer + autoplay toggle; compact end-of-session terminal summary.
**Independent test**: autoplay off → ideal not auto-played but replayable; session end prints
grade/coverage-first→final/top-fix/next-due from the same data written to the report.

- [x] T023 [US2] Honor `autoplay_ideal_answer` in the listen loop (`cli/practice.py`): when
  false, play the question but not the ideal answer; `r` still replays it on demand (FR-014).
- [x] T024 [US2] Add `render_summary(session, next_due)` to `session_ui.py`: compact box with
  grade, coverage first→final, top fix, next due date; degrade honestly when `analysis_pending`
  (no fabricated grade, FR-016). Print it after the report is written in `run_session`.
- [x] T025 [P] [US2] Tests in `tests/unit/test_session_ui.py`: summary content for a graded
  session and for a degraded/analysis-pending session; autoplay-off path leaves the ideal answer
  un-played but replayable.

**Checkpoint**: US1+US2 = the full P1 UX MVP; the report file is now optional reading.

---

## Phase 5: User Story 3 — Faster session, analysis quality untouched (P2)

**Goal**: background transcription overlap, pre-warm, follow-up reorder, engine-capability-gated
concurrent analysis producing a **byte-identical** report. **Independent test**: serial vs
concurrent reports byte-identical with stubbed engines (fixed outputs); one failed parallel call
degrades only its dimension; per-stage timings recorded.

- [x] T026 [US3] Background transcription overlap in `coordinator.py`: a single ASR worker
  thread transcribes attempt N while attempt N+1 records; never two Whisper jobs at once; results
  joined deterministically before analysis (FR-022). Mark overlapped stages in the StageTimer.
- [x] T027 [US3] Pre-warm ASR/VAD + `warm_output_device()` during the initial question/ideal
  playback (FR-023); guard so a load failure degrades to today's cold path, not a crash.
- [x] T028 [US3] Implement `src/speakloop/sessions/analysis.py`: `AnalysisJob(name, fn,
  depends_on)`, the DAG (grammar/mishearing/keypoints→coverage/coaching→consistency; gates per
  contracts/analysis-concurrency.md), a **serial** executor and a **concurrent** executor
  (`ThreadPoolExecutor(max_workers=cap)`), pure jobs → named result slots. Coverage speculated
  past the `phase==C` gate (discarded if grammar fails); store mutations happen on the caller
  thread post-join.
- [x] T029 [US3] Refactor the analysis block of `run_session` (`coordinator.py`) to build the
  job set, run it via the serial OR concurrent strategy (chosen by `analysis_parallel_safe`),
  then assemble the `Session` from the slots in the existing fixed field order (byte-identical
  guarantee, FR-027). Preserve per-call degradation exactly (FR-028).
- [x] T030 [US3] Reorder follow-up generation to fire the instant the final transcript + triage
  land (scheduled first); on a parallel-safe engine, run the interactive follow-up Q&A while the
  remaining analysis runs in the background pool; on a serial engine, generate-then-ask before
  grammar. Report-equivalent (follow-up entries independent of main grammar).
- [x] T031 [US3] Plumb `analysis_parallel_safe = getattr(engine, "parallel_safe", False)` +
  `analysis_concurrency` from `cli/practice.py` (and `resume.py`) into `run_session`; local stays
  serial regardless of cap.
- [x] T032 [US3] Instrument every stage with the `StageTimer` in `coordinator.py` (warm-up,
  per-attempt record/transcribe, follow-up generate, each analysis call, analysis group wall);
  attach `session.timings`; print the table when `timings_display` is set (T014).
- [x] T033 [US3] Serial-vs-concurrent **equivalence** test in
  `tests/integration/test_analysis_equivalence.py`: a stubbed engine returning fixed per-call
  outputs; run `run_session` analysis both ways; assert the written report bytes are identical
  (SC-006). Cover the speculative-coverage-discarded-on-grammar-failure case.
- [x] T034 [P] [US3] Degradation test: one concurrent call raises; assert the others' results are
  present and only that dimension is `analysis_pending` (FR-028); report still written.
- [x] T035 [P] [US3] Crash-safety test: simulate an abort mid-analysis; assert recordings +
  transcripts survive and the session is resumable (FR-029), matching today.
- [x] T036 [P] [US3] Timings test: with a fake clock, assert `session.timings` is recorded with
  the expected stage vocabulary and `analysis_mode`/`analysis_wall_seconds`; `--timings` prints.

**Checkpoint**: US3 delivers measured speed with the report provably unchanged.

---

## Phase 6: Polish & Cross-Cutting

- [x] T037 [P] Update/author module CLAUDE.md: `sessions/CLAUDE.md` (keyboard, session_ui,
  analysis), `audio/CLAUDE.md` (play_interruptible), `tts/CLAUDE.md` (prune), `feedback/CLAUDE.md`
  (timings), `llm/CLAUDE.md` (parallel_safe), `config/CLAUDE.md` (new loop keys), `cli/CLAUDE.md`
  (--timings, autoplay, keyboard consolidation).
- [x] T038 [P] Extend the help-without-models guard so importing the CLI still loads no engine
  package after the new modules land (`tests/integration/test_help_without_models.py`); keep all
  engine imports function-local.
- [x] T039 Update the root `CLAUDE.md` module table + traps for the new modules; re-measure the
  launch footprint stays ≤ 6000 tokens.
- [x] T040 Final measured before/after: run `research/measure_tts_asr.py` + a capped
  `research/measure_claude.py` (≤ remaining budget); fill the baseline-vs-after timings table and
  the manual voice-UX checklist into `RETURN_REPORT.md`.
- [x] T041 Full suite green (`uv run pytest -q`); confirm no test touches the real binary/mic/
  keyboard; ruff on changed files no worse than baseline.

---

## Dependencies & order

- **Setup (T001)** → **Foundational (T002–T014)** → **US1 (T015–T022)** → **US2 (T023–T025)** →
  **US3 (T026–T036)** → **Polish (T037–T041)**.
- US1 depends on foundational keyboard (T006), interruptible playback (T010), session_ui (T015).
- US3's equivalence/degradation gate (T033–T035) **must pass** before US3 counts as done.
- Within a phase, `[P]` tasks touch different files and may proceed together.

## Parallel opportunities

- Foundational T002/T004/T006/T008/T010/T012/T013 are all `[P]` (distinct files).
- US3 test tasks T034/T035/T036 are `[P]` once the executor (T028–T029) exists.

## Implementation strategy

1. **MVP = US1** (transparency/control) — shippable and valuable with zero speed change.
2. **+US2** completes the P1 UX (never-relisten + summary).
3. **+US3** adds measured speed behind the equivalence/degradation gate (the report never
   changes). Local default stays offline + byte-identical throughout.
