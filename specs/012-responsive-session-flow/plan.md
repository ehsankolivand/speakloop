# Implementation Plan: Responsive, Transparent & Faster Practice Session

**Branch**: `012-responsive-session-flow` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/012-responsive-session-flow/spec.md`

## Summary

Re-engineer the practice-session **flow** (not its analysis logic, prompts, or models) so the
learner always knows the state (playing / recording / transcribing / analyzing), can control it
with a single key (skip / replay / early-stop / skip-follow-up), is never forced to re-listen,
and gets a compact closing summary — and so the session is measurably faster on the stages the
measurement shows dominate. Speed is earned empirically: a stage timer + `--timings`, a warm
TTS cache (already content-addressed; add prune + overlap cold synth behind playback), background
transcription overlap, ASR pre-warm, follow-up generation kicked off the instant the final
transcript lands, and engine-capability-gated **concurrent** analysis (claude/openrouter
parallel-safe; local serial) that produces a **byte-identical** report. Zero new dependencies;
`schema_version` stays 1 (additive `timings` key); offline default unaffected; never lose a
recording.

## Technical Context

**Language/Version**: Python 3.12 (`requires-python >=3.12,<3.13`).

**Primary Dependencies**: `typer`, `rich` (state display, Live/Progress), `sounddevice` +
`soundfile` (playback/record), `numpy`. Stdlib only for the new mechanics: `termios`/`tty`/
`select` (raw keypress — existing precedent in `cli/practice._cbreak_read`), `threading` +
`concurrent.futures.ThreadPoolExecutor` (overlap + bounded concurrency), `time.perf_counter`
(timings), `hashlib`/`os` (TTS cache prune). **Zero new third-party dependencies** (FR-032).

**Storage**: Markdown reports with YAML frontmatter in `data/sessions/` (source of truth);
TTS clip cache under `~/.speakloop/cache/tts/`; derived JSON store under `~/.speakloop/`.

**Testing**: `pytest`. Every new seam (keyboard, clock, playback control, analysis executor) is
injectable; tests use fakes exclusively — never the real mic/speaker/keyboard or the real
`claude` binary (SC-008). Measurement harnesses (`research/measure_*.py`) are manual-only.

**Target Platform**: Apple Silicon macOS (Principle VII).

**Project Type**: Single-project CLI (`src/speakloop/…`).

**Performance Goals**: SC-001 launch-to-first-audio ≤ 5 s (warm cache); SC-002 ≤ 12 s final
attempt → first follow-up; SC-003 ≥ 40% analysis wall-clock reduction on parallel-safe engines;
SC-004 TTS skip ≤ 500 ms (measured `sd.stop()` ≈ 110 ms); SC-005 recording indicator 100% of
recording; SC-007 no unexplained silence > ~2 s.

**Constraints**: same prompts/models/schemas/report semantics; concurrency ⇒ byte-identical
report; recordings/transcripts survive a mid-analysis crash; per-call degradation stays per-call;
`schema_version` stays 1; offline default byte-identical.

**Scale/Scope**: one learner, one terminal session; ~6 analysis calls; 3 attempts + ≤2
follow-ups + ≤3 warm-up items per session.

## Constitution Check

*GATE: must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. English-only UI | ✅ | All new strings (state labels, hints, summary, `--timings`) are English. |
| II. Offline-First | ✅ | No network added. Concurrency uses local subprocess (claude) / the already-opt-in OpenRouter HTTP path; default local stays offline. |
| III. Privacy by Design | ✅ | No new data leaves the device; recordings/transcripts stay local; crash-safety preserved. |
| IV. Modular by Design | ✅ | New single-responsibility modules (`sessions/keyboard.py`, `sessions/analysis.py`, `sessions/session_ui.py`, `feedback/timings.py`), each with its own CLAUDE.md; cross-module talk via interfaces. |
| V. Swappable Engines | ✅ | No engine package imported outside its one wrapper. `parallel_safe` is a declared attribute on each engine; the coordinator stays engine-agnostic (reads a bool + cap). |
| VI. Resumable Downloads | ✅ | Untouched. |
| VII. Apple Silicon target | ✅ | termios/tty/select + CoreAudio behaviors measured on the M-series target. |
| VIII. Easy Install | ✅ | `speakloop --help` still loads no engine package (new modules keep engine imports function-local; the help-without-models guard extends to new modules). |
| IX. Obsidian reports | ✅ | `timings` is additive optional; `schema_version` stays 1; filename/format unchanged. |
| X. Research in repo | ✅ | `research.md` carries the empirical baseline; no engine swap, so no `doc/research_*.md` change required (none of TTS/ASR/LLM engine *selection* changes). |
| XI. AI-collaborator friendly | ✅ | New modules are small, loadable units with their own CLAUDE.md; the root map's module table is updated. |
| XII. Iterative Delivery | ✅ | US1 (transparency) ships and is valuable with zero speed change; US2 (summary) and US3 (speed) layer on without breaking earlier slices. |

**Non-negotiable constraints**: Python 3.12 ✅ · `uv` only ✅ · models under `~/.speakloop` ✅ ·
YAML user config (the two new loop.yaml keys) ✅ · CLI-only `rich` UI (no GUI) ✅ · no external
services ✅ · MIT ✅. **No violations — Complexity Tracking left empty.**

## Project Structure

### Documentation (this feature)

```text
specs/012-responsive-session-flow/
├── plan.md              # This file
├── spec.md              # Feature spec (+ Clarifications)
├── research.md          # Phase 0: empirical baseline + ranked optimizations + decisions
├── data-model.md        # Phase 1: entities + the additive timings key
├── quickstart.md        # Phase 1: learner + developer walkthrough
├── contracts/           # Phase 1: keyboard/states, analysis-concurrency, loop-config/timings
│   ├── keyboard-and-states.md
│   ├── analysis-concurrency.md
│   └── loop-config-and-timings.md
├── research/            # Phase 0: measurement harnesses + captured numbers (committed)
│   ├── measure_tts_asr.py
│   ├── measure_claude.py
│   └── claude_timings.json
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/speakloop/
├── audio/
│   └── playback.py            # + play_interruptible(...), warm_output_device()
├── sessions/
│   ├── coordinator.py         # rewire: states, countdown, background transcription,
│   │                          #   reorder follow-ups, analysis executor hand-off
│   ├── keyboard.py            # NEW: KeyReader (Raw/Null/Fake) — the one raw-input module
│   ├── session_ui.py          # NEW: one-state-at-a-time rich display + countdown + summary
│   ├── analysis.py            # NEW: analysis DAG + serial/concurrent executors (equivalence)
│   └── CLAUDE.md              # updated
├── feedback/
│   ├── timings.py             # NEW: StageTimer (injectable clock) → frontmatter + --timings
│   └── frontmatter.py         # + Session.timings additive optional key
├── tts/
│   └── cache.py               # + prune(max_bytes) size-cap policy
├── config/
│   └── loop_config.py         # + autoplay_ideal_answer, analysis_concurrency
├── llm/
│   ├── qwen_engine.py         # + parallel_safe = False
│   ├── openrouter_engine.py   # + parallel_safe = True
│   └── claude_code_engine.py  # + parallel_safe = True
└── cli/
    ├── main.py                # + --timings on practice/resume
    └── practice.py            # plumb --timings, autoplay toggle, parallel_safe + cap;
                               #   build/inject KeyReader; consolidate _cbreak_read into keyboard.py

tests/
├── unit/                      # keyboard control paths, timings, cache prune, state display
├── integration/              # serial-vs-concurrent report equivalence, degradation-with-failure
└── fixtures/wav/…            # existing fixtures reused
```

**Structure Decision**: Single-project CLI, reusing the existing module layout. New code lands
in four new small modules plus targeted edits to `coordinator.py`, `playback.py`, `cache.py`,
`frontmatter.py`, `loop_config.py`, the three engine wrappers, and the CLI. No rewrite.

## Phase 0 — Research (empirical; see research.md)

1. Built measurement harnesses; ran the instrumented pipeline over fixture audio + capped real
   `claude` calls; produced the baseline table.
2. Resolved: TTS streaming capability (`generate_stream` exists), safe mid-stream playback
   interruption (`sd.stop()` ≈ 110 ms), raw-mode fallback detection (no-tty ⇒ `NullKeyReader`).
3. Ranked optimizations by **measured** impact and chose which to adopt vs drop (streaming
   dropped in favor of cache+overlap). Full numbers + decisions in `research.md`.

## Phase 1 — Design & Contracts

- `data-model.md`: the additive `timings` key + the in-memory orchestration entities.
- `contracts/`: keyboard & states; analysis concurrency & report equivalence; loop-config &
  timings.
- Agent context: the root `CLAUDE.md` SPECKIT block is updated to make 012 the active feature.

## Phase 2 — Tasks (via /speckit-tasks)

Foundational (stage timer + timings key/flag; `KeyReader` + fake; TTS cache prune;
`play_interruptible` + warm; engine `parallel_safe` flags) → US1 (states + countdown + indicator
+ controls + autoplay toggle + closing summary) → US2/US3 (background transcription overlap, ASR
pre-warm, follow-up reorder, concurrent analysis executor with equivalence + degradation gates,
final measured before/after). Equivalence + degradation tests are a hard gate on the speed work.

## Complexity Tracking

No constitution violations — section intentionally empty.
