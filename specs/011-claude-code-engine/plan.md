# Implementation Plan: Claude Code Analysis Engine

**Branch**: `011-claude-code-engine` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-claude-code-engine/spec.md`

## Summary

Add a third `LLMEngine` implementation — `ClaudeCodeEngine` — that drives the learner's locally
installed, logged-in **Claude Code** CLI in non-interactive print mode via `subprocess` (stdlib
only, no SDK). It is selected with `--engine local|openrouter|claude` on `practice`/`resume`
(`--cloud` preserved as an alias for `--engine openrouter`) or via a one-line loop-config default.
Every analysis call in the pipeline routes through it with **zero call-site changes and zero
prompt/schema changes** — the engine sits behind the existing injected interface exactly like the
Qwen and OpenRouter engines. Calls bill to the learner's subscription (the engine strips
`ANTHROPIC_API_KEY` and related override vars so billing never silently switches to pay-per-token).
P2 adds a small static call-site→tier→model map (fast=haiku for mishearing/drills, strong=sonnet for
the reasoning-heavy calls), overridable in the loop config, wired by constructing one engine per tier.

## Technical Context

**Language/Version**: Python 3.12 (pinned `>=3.12,<3.13`).

**Primary Dependencies**: **None new.** Standard library `subprocess`, `json`, `os`, `shutil`. The
engine confines the only `subprocess` invocation of the `claude` binary to one wrapper file
(`llm/claude_code_engine.py`), mirroring how `openrouter_engine.py` is the only `urllib` caller
(Principle V). The Python `claude-agent-sdk` is the considered-and-rejected alternative (see
research.md): extra dependency, same underlying CLI, same credit coverage.

**Storage**: No new store. Additive optional keys in the existing loop config
(`~/.speakloop/loop.yaml`): `engine`, `claude_fast_model`, `claude_strong_model`. Report
`schema_version` stays 1; no frontmatter keys added. Session files and the derived store are
untouched.

**Testing**: `pytest`. All automated tests run against an **injected fake runner** (a callable
returning canned `ClaudeCliResult` objects) or monkeypatched probes — **no automated test ever
invokes the real `claude` binary** (Constitution: "Live model calls in tests are forbidden").

**Target Platform**: Apple Silicon macOS (Principle VII). Observed CLI: `claude` **2.1.170**.

**Project Type**: Single-project CLI (existing `src/speakloop/` layout).

**Performance Goals**: One subprocess per `generate()` call, hard timeout default ~90 s. Observed
haiku latency ~2–3 s/call; a full session (~8 analysis calls) is well within an interactive budget.

**Constraints**: Offline-first default unchanged (the claude path is opt-in, like `--cloud`).
Billing safety is a hard requirement (env stripping). `speakloop --help` stays model-free (engine
import is function-local).

**Scale/Scope**: One new engine file + small CLI/config/doctor wiring. Single-user. ~8 analysis call
sites, all already injected.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|-----------|--------|------|
| I. English-Only UI | ✅ PASS | All new strings (doctor rows, warnings, errors) are English. |
| II. Offline-First | ✅ PASS | The claude path is **opt-in** (flag/config), exactly like the `--cloud` exemption established by feature 008. The default (no flag) path makes zero network calls and stays byte-identical. |
| III. Privacy by Design | ✅ PASS | Transcripts are sent to Claude Code (→ Anthropic) only on the opt-in claude path; a one-time privacy disclosure mirrors cloud mode. Audio + reports never leave the device. |
| IV. Modular by Design | ✅ PASS | New code is one wrapper file in `llm/` plus thin CLI/config/doctor wiring; `llm/CLAUDE.md` is updated in the same change. |
| V. Swappable Engines | ✅ PASS | `claude_code_engine.py` is the ONLY file that spawns the `claude` subprocess; selecting it touches only the CLI builder. `generate()` signature unchanged; no engine config leaks to call sites. |
| VI. Resumable Downloads | ✅ N/A | No model download (Claude Code is user-installed). |
| VII. Apple Silicon | ✅ PASS | Verified against the installed macOS CLI. |
| VIII. Easy Install | ✅ PASS | Engine import is function-local; `--help`/`--version` stay model-free (guarded by existing test). |
| IX. Obsidian Reports | ✅ PASS | No report-format change; `schema_version` stays 1; no new frontmatter. |
| X. Research in Repo | ✅ PASS | research.md records the CLI empirical findings; no `doc/research_*.md` engine doc needs changing (this is a delivery channel for the same analysis, not a new model). |
| XI. AI-Collaborator Friendly | ✅ PASS | New module is self-contained with its own doc; no widening of cross-module context. |
| XII. Iterative Delivery | ✅ PASS | P1 (engine) ships independently; P2 (tiering) bolts on without rework. |
| Constraint: zero new deps | ✅ PASS | stdlib only. |
| Constraint: YAML config | ✅ PASS | New keys live in `loop.yaml`. |

**Result: PASS — no violations.** Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/011-claude-code-engine/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 — empirical CLI findings + decisions
├── data-model.md        # Phase 1 — entities (engine, selection, tier map, error taxonomy)
├── quickstart.md        # Phase 1 — how to use + verify
├── contracts/
│   ├── engine-interface.md   # ClaudeCodeEngine ↔ LLMEngine contract + error taxonomy
│   ├── cli-commands.md       # --engine / --cloud-alias / config default + doctor rows
│   └── loop-config.md        # additive loop.yaml keys
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/speakloop/
├── llm/
│   ├── interface.py            # UNCHANGED — LLMEngine Protocol + LLMEngineError
│   ├── qwen_engine.py          # UNCHANGED — local default
│   ├── openrouter_engine.py    # UNCHANGED — cloud
│   ├── claude_code_engine.py   # NEW — the only file that spawns the `claude` subprocess
│   └── CLAUDE.md               # UPDATED — document the third engine
├── config/
│   └── loop_config.py          # UPDATED — additive engine + tier-model keys + resolver
└── cli/
    ├── main.py                 # UPDATED — --engine option on practice + resume (--cloud alias)
    ├── practice.py             # UPDATED — engine resolution; _build_claude_grammar_analyzer;
    │                           #           _build_runners gains optional fast_engine kwarg
    ├── resume.py               # UPDATED — engine selection branch
    └── doctor.py               # UPDATED — Claude Code rows (binary/version/auth/default engine)

tests/
├── contract/
│   └── test_llm_interface.py   # UPDATED — parametrize contract over ClaudeCodeEngine (fake runner)
├── unit/ (or llm/)
│   ├── test_claude_code_engine.py   # NEW — runner, error taxonomy, env-stripping, retry, tiering
│   └── test_engine_selection.py     # NEW — --engine/--cloud/config precedence resolver
└── integration/
    ├── test_claude_engine_degradation.py  # NEW — stubbed coordinator → analysis_pending
    └── test_doctor_claude_rows.py         # NEW — doctor rows via monkeypatched probe
```

**Structure Decision**: Single-project CLI; the new engine is one wrapper file in the existing
`llm/` module, consistent with `qwen_engine.py` and `openrouter_engine.py`. No new module is
created — the engine belongs in `llm/` and the wiring belongs in `cli/` and `config/`.

## Phase 0 — Research

See [research.md](./research.md). All unknowns resolved empirically against the installed CLI
(`claude 2.1.170`). Key decisions: subprocess + stdlib (reject SDK); `--safe-mode` (NOT `--bare`,
which breaks subscription OAuth) + `--tools ""` + `--system-prompt` + `--no-session-persistence` +
`--output-format json`; key off `is_error` (not `subtype`); output text in `.result` (fences
stripped by the existing recovery ladder); error taxonomy from FileNotFoundError / TimeoutExpired /
`is_error` text / parse-failure; credit-free auth check via `claude auth status --json`; strip
`ANTHROPIC_API_KEY` and related override vars for billing safety.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md): `ClaudeCodeEngine`, `ClaudeCliResult`, the `LLMEngineError`
  subclasses (not_installed / not_authenticated / rate_limited / timeout / bad_output), the
  engine-selection precedence, and the call-site→tier→model map.
- [contracts/engine-interface.md](./contracts/engine-interface.md): the `generate()` contract,
  argv construction (named constants pinned to `claude 2.1.170`), envelope parsing, retry, and the
  env-stripping guarantee.
- [contracts/cli-commands.md](./contracts/cli-commands.md): `--engine`/`--cloud` precedence and the
  four new doctor rows.
- [contracts/loop-config.md](./contracts/loop-config.md): additive `engine`, `claude_fast_model`,
  `claude_strong_model` keys.
- [quickstart.md](./quickstart.md): set-once config + smoke commands.

## Phase 2 — Tasks

Generated by `/speckit-tasks` into tasks.md (tight: well under 20 tasks). Foundational (runner +
error taxonomy + fake harness) → P1 (engine + plumbing + env-stripping + doctor + wiring) → P2
(tier map + config override) → tests → live verification.

## Complexity Tracking

*No constitution violations — table intentionally empty.*
