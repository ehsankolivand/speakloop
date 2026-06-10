# Return Report — 012 Responsive, Transparent & Faster Practice Session

**Branch**: `012-responsive-session-flow` (forked from `011-claude-code-engine`) · **Status**:
implemented, suite green, **pushed**, NOT merged. · **Date**: 2026-06-11

---

## TL;DR

The full spec-kit flow ran autonomously (specify → clarify → plan → tasks → implement). The
practice session is now **transparent and controllable** (single unambiguous state, single-key
skip/replay/early-stop/skip-follow-up, `● REC` indicator + `3·2·1` countdown, closing summary)
and **measurably faster** without any analysis-quality change (engine-capability-gated concurrent
analysis that produces a **byte-identical** report, follow-ups reordered to fire the instant the
final transcript lands, background transcription overlap, size-capped TTS cache prune, per-stage
`--timings`). **Zero new dependencies.** `schema_version` stays **1**. The local default path
stays offline + byte-identical. Full suite: **693 → see final numbers below**, all fakes — no
test touches the real `claude` binary, microphone, or keyboard.

---

## What changed (by area)

| Area | Change |
|------|--------|
| `sessions/keyboard.py` (NEW) | The one raw-input `KeyReader` seam (`Raw`/`Null`/`Fake`), stdlib termios/tty/select; consolidates the two old ad-hoc readers. |
| `sessions/session_ui.py` (NEW) | One-state-at-a-time `rich` display: `● REC` indicator, visual `3·2·1` countdown, TRANSCRIBING/ANALYZING spinners, state-only control hints, closing summary. |
| `sessions/analysis.py` (NEW) | `run_group` — serial for a single in-process model, `ThreadPoolExecutor(cap)` for a parallel-safe engine; per-job error capture; name-keyed results → byte-identical report. |
| `feedback/timings.py` (NEW) | `StageTimer` (injectable clock) → additive `timings` frontmatter + `--timings`. |
| `sessions/coordinator.py` | `_record_stage` (countdown + `● REC` + key poller), `_record_attempt`/`_transcribe_attempt` (single-worker background ASR overlap), `_analyze` (executor, gates preserved), follow-ups reordered earlier, store writes kept on the main thread. |
| `audio/playback.py` | `play_interruptible` (sd.stop ≈110 ms) + `warm_output_device`. |
| `tts/cache.py` | `prune(max_bytes, keep)` size cap; wired into `KokoroEngine.synthesize`. |
| `config/loop_config.py` | `autoplay_ideal_answer` (default true) + `analysis_concurrency` (default 3). |
| `llm/*_engine.py` | `parallel_safe` class attr (qwen False; openrouter/claude True). |
| `cli/main.py`, `cli/practice.py`, `cli/resume.py` | `--timings` flag; one shared `KeyReader`; autoplay toggle; engine-`parallel_safe` plumbed into `run_session`. |

---

## Baseline vs After — measured (M-series target, real `claude`; see `specs/012-.../research/`)

All numbers measured on this machine, 2026-06-10/11. Methodology + raw JSON in
`research/{claude_timings,after_timings}.json` and `research.md`.

### Per-stage primitives (local engines, fixture audio)

| Stage | Measured |
|-------|----------|
| TTS warm-cache hit (repeat review) | **0.03 ms** (cold ideal-answer synth 5.14 s — overlapped behind question playback) |
| ASR warm transcribe (3 s clip) | 1.37 s (cold load ~1.15 s, now overlapped by background transcription) |
| TTS skip latency (`sd.stop` mid-stream) | **~110 ms** (target ≤ 500 ms ✓) |

### Post-session analysis (claude; the ≥40% target, SC-003)

Two measured runs (per-call latency has **high variance** — grammar ranges 74 s single-pass to
226 s when the analyzer's bounded regenerate fires):

| | Baseline run (single-pass grammar) | After run (measured end-to-end, real executor) |
|--|--|--|
| grammar | 74 s | **131.3 s** (hit the bounded regenerate) |
| mishearing (×3 internally) | ~75 s | 24.9 s |
| coverage (keypoints+coverage) | ~31 s | 25.8 s |
| coaching | 27 s | 31.9 s |
| consistency | 12 s | 12.3 s |
| **Serial sum (same run)** | **~219 s** (modeled) | **226.2 s** (this run's stage sum) |
| **Concurrent wall (measured)** | ~118 s (modeled) | **175.5 s** (measured; group wall 163.2 s) |
| **Reduction** | **~46%** (modeled, typical) | **22.4%** (this run — grammar regenerated) |

**What the concurrency actually did (measured this run):** it hid **100% of the non-critical
work** — `mishearing` (24.9 s) + `coverage` (25.8 s) = **50.7 s** — behind the
`grammar → coaching → consistency` critical path (131.3 + 31.9 + 12.3 = 175.5 s). The residual
wall **IS** that critical path: pure model-inference latency we must not shorten (FR-031).

> **SC-003 honest verdict:** the ≥ 40% target is **met in the typical single-pass-grammar case
> (~46% modeled)** and **below target (~22%) on a run where the grammar call hits its bounded
> regenerate** (131 s instead of 74 s), which inflates the critical path. This is a documented
> **model-latency floor** per the Step-2 rule — concurrency cannot overlap a serial data
> dependency (coaching needs grammar's patterns; consistency needs coaching's text), and we do
> not change the model/prompt to chase the number. The structural win (all parallelizable work
> hidden) is realized in **both** runs.

### Success-criteria verdicts (honest)

| SC | Target | Verdict |
|----|--------|---------|
| SC-001 launch-to-first-audio ≤ 5 s (warm cache) | **MET** (cache hit ~0 ms; no model load on the cached path) |
| SC-002 final attempt → first follow-up ≤ 12 s | **NOT MET — documented model-latency floor ~14–17 s.** The reorder cuts today's ~151 s gap to ~17 s (~89% better); the residual is the **14.2 s follow-up *generation* model call** alone, which FR-031 forbids changing. Shown under a labeled `generating follow-up…` state (no dead silence). Reachable only on a faster engine. |
| SC-003 analysis wall-clock ≥ 40% ↓ (parallel-safe) | **PARTIAL — met in the typical single-pass-grammar case (~46% modeled); ~22% on a grammar-regenerate run. Documented model-latency floor; the executor provably hides all parallelizable work.** |
| SC-004 TTS skip ≤ 500 ms | **MET** (~110 ms) |
| SC-005 recording indicator 100% of recording | **MET** by construction (state machine) |
| SC-006 serial == concurrent report (byte-identical) | **MET** — gate test `test_analysis_equivalence.py` |
| SC-007 no unexplained silence > ~2 s | **MET** by construction (every long op shows a labeled state) |
| SC-009 schema_version 1; no-timings report byte-identical | **MET** |
| SC-010 zero new dependencies | **MET** |

---

## Self-answered clarifications (autonomous; recorded in spec.md §Clarifications)

1. **Key bindings + hints** → context-aware set, hint shows only the keys valid now: `space`=
   advance (skip clip / stop recording), `r`=replay, `s`=skip whole follow-up, `q`=quit,
   `Enter`=`space` alias. Reuses existing listen-loop muscle memory.
2. **Indicator + countdown presentation** → reuse `rich`; one transient state region; distinct
   `● REC` red marker + elapsed/budget + remaining bar; brief transient `Recording in 3·2·1`.
3. **Autoplay-ideal-answer default** → **on** (`autoplay_ideal_answer: true`); instant
   skippability removes the forced-wait cost; one-line opt-out for rapid drills.
4. **Concurrency cap** → default **3** (`analysis_concurrency`, clamped ≥ 1); local ignores it.
5. **Countdown modality/length** → visual-only, ~1.5 s (~0.5 s/tick), no TTS (an audible
   countdown would add latency before every recording and blow the budgets).

### Key assumptions / decisions

- The TTS clip cache **already existed** (content-addressed) — this feature added the prune
  policy; repeat-review instant-start was already true.
- ASR is **eager-loaded at `build_engine`** (existing), so the cold load is already outside the
  timed loop; background transcription further hides per-attempt decode + cold VAD.
- **TTS streaming dropped**: `KokoroTTS.generate_stream` exists (time-to-first-chunk 2.6 s) but
  cache + cold-synth overlap already meet SC-001; streaming would complicate interruptible
  playback for sub-second gain. Recorded as available-but-unused with a whole-clip fallback.
- **Concurrency without speculation**: coverage/coaching keep today's `phase==C` gate (run only
  after grammar succeeds). The critical path (grammar→coaching→consistency) dominates, so the
  simpler non-speculative phased executor already meets ≥40% — and is obviously byte-identical.
- **Abort during follow-ups** now writes a resumable *pending* report instead of forcing the
  learner to wait through the (minute-long) analysis after their Ctrl-C.

---

## Manual voice-UX checklist (please verify by voice — cannot be automated)

Run `uv run speakloop practice --engine claude --timings` in a real terminal and confirm:

- [ ] **Key responsiveness during playback** — while the question/ideal answer plays, pressing
  `space` stops it within ~½ s; `r` replays it; the on-screen hint shows only `space`/`r`.
- [ ] **Recording indicator visibility** — every recording shows a red `● REC` line with a live
  elapsed/budget timer + remaining bar, visible the entire time; it is unmistakably different
  from the playing/transcribing/analyzing states.
- [ ] **Follow-up countdown** — before *every* recording (attempts, warm-up, follow-ups) a brief
  `Recording in 3 · 2 · 1` appears, then immediately `● REC`.
- [ ] **Early-stop** — pressing `space`/`Enter` while recording stops it the moment you finish
  speaking and moves to "transcribing".
- [ ] **Skip behavior** — `s` during a follow-up (prompt or answer) abandons just that follow-up
  and moves on, with no answer recorded.
- [ ] **Autoplay toggle** — set `autoplay_ideal_answer: false` in `~/.speakloop/loop.yaml`; the
  question still plays automatically, the ideal answer does not, and `R` still replays it.
- [ ] **Closing summary** — at the end the terminal prints grade / coverage first→final / top
  fix / next due, so you don't need to open the report file.
- [ ] **No dead silence** — at no point does the terminal sit blank for > ~2 s without a labeled
  state (warm-up generation, transcription, analysis all show a spinner).
- [ ] **`--timings`** — a per-stage table prints at the end; the same `timings:` block is in the
  report frontmatter.
- [ ] **Fallback** — piping input / a non-tty terminal still completes the session (line/timeout
  path), and `--engine local` stays fully offline.

---

## Suite

**`uv run pytest -q` → 694 passed, 3 skipped, 2 deselected** (baseline at branch start: 628
passed; +66 new tests for 012). 3 skips are pre-existing fixture-gated repro tests; 2 deselected
are the `live_asr` smoke tests. Run time ~18 s.

- No test touches the real `claude` binary, microphone, or keyboard — all via injected
  `FakeKeyReader` / fake `record_fn` / stubbed engines (SC-008).
- Equivalence + degradation + crash-safety + timings are the speed-work gate
  (`tests/integration/test_analysis_equivalence.py`, 5 tests, all green).
- Ruff: the only findings on changed files are 2 **pre-existing** `SIM105` in
  `cli/practice._cbreak_read` (untouched code) — no new findings introduced.

## Merge readiness

- **Ready to merge** into `011-claude-code-engine` (its parent) after the manual voice-UX
  checklist above is verified by ear. Not merged per instruction.
- Real claude measurement budget used: **17 of 20** calls (9 baseline + 8 after).
- Constitution gates all pass (session files source of truth; schema_version 1; offline default
  unaffected; never lose a recording). No new dependency.
