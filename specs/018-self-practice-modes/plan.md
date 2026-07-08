# Implementation Plan: Offline Self-Practice Modes — Rescue-Lines Deck & Answer Shadowing

**Branch**: `018-self-practice-modes` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/018-self-practice-modes/spec.md`

## Summary

Add two additive, offline, standalone CLI trainers modeled on `speakloop pronounce`:

- **Mode A — `speakloop deck`** (P1): a self-graded spaced-repetition trainer for the learner's own corrected lines. Cards are **derived deterministically from the structured grammar evidence already in session reports** (`grammar_patterns[].evidence[]{quote, corrected}` — the "You said"/"Better:" pairs) plus a bundled starter set of interview discourse chunks. A hear → say → see → self-mark loop reschedules each card on the **existing SRS interval ladder** (`srs.schedule`), with per-card state persisted in a new additive **default-empty `line_cards` store section**. An offline `--export` writes the whole deck as Anki cloze cards (`{{c1::…}}` + rule hint). TTS-only: no ASR, no phoneme scorer, no microphone.
- **Mode B — `speakloop shadow`** (P2): a sentence-by-sentence shadowing trainer over a question's `ideal_answer`. An abbreviation-aware splitter yields sentences; for each, TTS speaks it, the learner repeats, the resident ASR transcribes, and **deterministic offline feedback** reports content-word completeness (warm-up-judge style) plus pace/fillers from `metrics.compute_all`. Provisions TTS + ASR (installer Phase B), **not** the phoneme scorer; writes no report; ephemeral.

Both reuse the injectable command skeleton and record/teach closures of `cli/pronounce.py` and the pure loop shape of `pronunciation.drill_runner`, keep all engine imports function-local, and hold `schema_version`/`STORE_VERSION` at 1.

## Technical Context

**Language/Version**: Python 3.12 (pinned `>=3.12,<3.13`), package manager `uv` only.

**Primary Dependencies**: `typer`, `rich` (CLI/UI); `pyyaml` (config + starter cards); existing engine wrappers reused **function-local** — `tts.kokoro_engine.KokoroEngine`, `asr.selection.build_engine` (Whisper/Parakeet), `audio.playback`/`audio.recorder`, `sessions.keyboard`. No new third-party dependency. No new engine package.

**Storage**: Derived JSON store `~/.speakloop/store.json` (adds one default-empty `line_cards` section; `STORE_VERSION` stays 1). Reads existing `data/sessions/*.md` reports (Mode A card source). Bundled `starter_cards.yaml` shipped in the package. Optional new `loop.yaml` key `deck_daily_capacity` (default 20). No report written by either mode (`schema_version` untouched).

**Testing**: `pytest` (unit + CLI-with-fakes, mirroring `tests/unit/cli/test_pronounce_command.py`); `mypy` (pure-logic gate — add `linecards` + `shadowing` packages to `[tool.mypy].files`); `ruff` (no new findings). No live models/mic/keyboard in tests (rule O9).

**Target Platform**: Apple Silicon macOS (Principle VII); reuses the resident engines already used by `practice`/`pronounce`.

**Project Type**: Single-project CLI (existing `src/speakloop/<module>/` layout).

**Performance Goals**: Interactive, user-paced; no throughput target. Card derivation and sentence splitting are pure and run over local files in well under a second for realistic corpora.

**Constraints**: Offline after model download (Principle II); English-only (Principle I); CLI-only, no GUI; recordings deleted after use (Principle III); `--help` loads no engine (Principle VIII, guarded by `tests/integration/test_help_without_models.py`); function-local engine imports only (Principle V, guarded by `tests/unit/asr/test_engine_import_isolation.py`).

**Scale/Scope**: Single local user. Deck size bounded per run (default 20); starter set ≥ 8 cards; a handful of Android questions today (shadow operates on whatever the resolved Q&A file holds).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

The project constitution (`.specify/memory/constitution.md`, v1.1.0) plus the root-`CLAUDE.md` hard invariants are walked explicitly. **Result: PASS — no violations, no relaxations requested.**

| # | Principle / Invariant | How this feature satisfies it |
|---|---|---|
| I | English-Only UI | All prompts, feedback, summaries, and the bundled `starter_cards.yaml` are English only. No L1, no localization layer. |
| II | Offline-First | Both modes make **zero network calls** after the one-time model download. No telemetry/analytics. `deck` needs only local TTS; `shadow` needs local TTS+ASR. Feedback is deterministic (no cloud/LLM). |
| III | Privacy by Design | `deck` records nothing (self-graded). `shadow` records each repeat to a scratch WAV and **deletes it after transcription** (reusing the `drill_runner._score_once` `wav_path.unlink()` discipline). No file is uploaded. |
| IV | Modular by Design | Two new single-responsibility modules — `linecards/` (Mode A pure logic) and `shadowing/` (Mode B pure logic) — **each ships a `CLAUDE.md`**. Thin `cli/deck.py` + `cli/shadow.py` orchestrate; the loop/engine seams are injected (testable without models). |
| V | Swappable Engines | No engine-specific import at any new module's top level. TTS/ASR reused via their existing single wrapper files, imported **function-local** inside command bodies. Replacing an engine still touches exactly one wrapper. Guarded by the import-isolation tests. |
| VI | Resumable Downloads | Provisioning reuses `installer.ensure_models(...)` unchanged (resumable). No new download path. |
| VII | Apple Silicon Primary | Reuses the resident MLX engines; no new hardware assumption. |
| VIII | Easy Install for Everyone | `speakloop --help` and both new `--help` screens work with **no models present** (function-local engine imports). No new install/`pip` step; `uv run speakloop deck/shadow`. |
| IX | Obsidian-Compatible Reports | Neither mode writes a session report → report format untouched, **`schema_version` stays 1**, no frontmatter key added. |
| X | Research is Part of the Repo | **No engine is added or swapped**, so no `research_*.md` engine update is required. The pedagogy is already documented: `doc/research_methodology.md` §2.2 (shadowing) and §3.4 (productive-cloze cards on the learner's own error inventory). Plan references these; a short pointer note may be appended (non-gating). |
| XI | AI-Collaborator Friendly | New modules are small, loadable units with their own `CLAUDE.md`; root `CLAUDE.md` map + module table updated in the same commits (anti-rot). |
| XII | Iterative Delivery | US1 (`deck`) and US2 (`shadow`) are independent MVPs: each ships and delivers value alone; neither blocks the other. |
| — | **`schema_version` stays 1** | No report is written; no frontmatter change. |
| — | **`STORE_VERSION` stays 1** | `line_cards` is a **default-empty additive** section (old stores load it as `{}`; old code ignores it) — identical to how 017 added `pronunciation_contrasts`. |
| — | **Store rebuildable from reports** | `line_cards` card **content** is re-derived from report grammar evidence on `speakloop rebuild`; the per-card SRS scheduling state resets to a placeholder — the **same accepted trade-off** as `schedule.next_due` and `pronunciation_contrasts` (documented in `store/CLAUDE.md`). |
| — | **No module-level engine import** | Enforced; new CLI modules import engines function-local. Import-isolation tests extended to cover them. |
| — | **Immutable specs 001–017** | Untouched. This is `specs/018-*`. |
| — | **Anti-rot (v1.1.0)** | Every behavior-changing commit updates its owning context file in the same commit: new `linecards/CLAUDE.md` + `shadowing/CLAUDE.md`; edits to `store/CLAUDE.md`, `srs/CLAUDE.md`, `cli/CLAUDE.md`, `config/CLAUDE.md`, and the root map. |
| — | **YAML-only user config** | The one optional new key (`deck_daily_capacity`) is added to `loop.yaml` via the established `_int` clamp in `loop_config.load()`; no TOML/JSON/env. |

**One noted design choice (not a violation):** the SRS interval ladder is reused *generically* by extracting the pure recurrence from `srs.schedule.next_due` into a shared `srs.schedule.advance(...)` helper that both question-scheduling and line-card scheduling call. This is a **behavior-preserving refactor** of existing 010 source (not an immutable spec artifact); the existing `srs` unit tests pin `next_due`'s behavior and must stay green, proving the ladder is unchanged (single tuning surface preserved).

## Project Structure

### Documentation (this feature)

```text
specs/018-self-practice-modes/
├── spec.md              # /speckit-specify output (committed)
├── plan.md              # this file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — LineCard, StarterCard, store section, shadow entities
├── contracts/
│   ├── deck-command.md   # `speakloop deck` CLI contract
│   └── shadow-command.md # `speakloop shadow` CLI contract
├── quickstart.md        # Phase 1 — how to run + verify both modes
└── checklists/
    └── requirements.md  # spec quality checklist (committed)
```

### Source Code (repository root)

```text
src/speakloop/
├── linecards/                 # NEW — Mode A pure logic (mypy-gated, no engine import)
│   ├── __init__.py            #   public API: derive_cards, select_due, advance_card, to_anki, load_starter_cards
│   ├── cards.py               #   LineCard dataclass + stable card_id + derive_cards(reports) + merge with stored SRS state
│   ├── cloze.py               #   cloze_from_correction(quote, corrected) -> str  (word-diff → {{c1::…}}) + Anki line format
│   ├── deck.py                #   due-selection (mirrors srs.queue priority) + run-cap
│   ├── starter.py             #   load + validate bundled starter cards
│   ├── starter_cards.yaml     #   bundled starter discourse chunks (English-only, >= 8)
│   └── CLAUDE.md              #   module contract (Principle IV)
├── shadowing/                 # NEW — Mode B pure logic (mypy-gated, no engine import)
│   ├── __init__.py            #   public API: split_sentences, judge_completeness
│   ├── split.py               #   abbreviation-aware sentence splitter
│   ├── judge.py               #   content-word completeness (normalize + stopwords + coverage)
│   └── CLAUDE.md              #   module contract (Principle IV)
├── cli/
│   ├── deck.py                # NEW — thin orchestrator: provision Phase A -> TTS/play/keys -> derive+merge -> hear/say/see/self-mark -> persist; --export path
│   ├── shadow.py              # NEW — thin orchestrator: provision Phase B -> TTS+ASR/play/record/keys -> pick question -> split -> hear/repeat/transcribe/judge+metrics
│   ├── main.py                # EDIT — register `deck` + `shadow` commands (function-local imports of the thin modules)
│   └── CLAUDE.md              # EDIT — document the two commands
├── srs/
│   ├── schedule.py            # EDIT — extract pure `advance(...)`; `next_due` calls it (behavior-preserving); line-card scheduler calls it too
│   └── CLAUDE.md              # EDIT — note the shared `advance` helper
├── store/
│   ├── model.py               # EDIT — add default-empty `line_cards` section + to_dict/from_dict + helpers; STORE_VERSION stays 1
│   ├── rebuild.py             # EDIT — fold `line_cards` from report evidence (content rebuildable; SRS placeholder)
│   └── CLAUDE.md              # EDIT — document `line_cards` (rebuildable-content / live-scheduling trade-off)
└── config/
    ├── loop_config.py         # EDIT — add optional `deck_daily_capacity` (default 20, floor 1) via `_int`
    └── CLAUDE.md              # EDIT — add the key to the loop.yaml table

tests/
├── unit/
│   ├── linecards/             # NEW — derive, cloze, deck-selection, starter loader, card scheduling
│   ├── shadowing/             # NEW — split (abbreviation cases), judge (coverage/missed words)
│   ├── srs/                   # EDIT — add advance() behavior-preserving test (next_due unchanged)
│   └── store/                 # EDIT — line_cards round-trip + rebuild fold
├── unit/cli/
│   ├── test_deck_command.py   # NEW — fakes (TTS/play/keys/store); loop order, self-mark reschedule, export, non-interactive skip, no report
│   └── test_shadow_command.py # NEW — fakes (TTS/ASR/record/keys); split->speak->transcribe->judge, not-captured, no report, no residual wav
└── integration/
    └── (existing test_help_without_models.py + test_engine_import_isolation.py cover the new modules; extend assertions to name `cli/deck.py` + `cli/shadow.py`)
```

**Structure Decision**: Single-project CLI. Two new pure-logic modules (`linecards/`, `shadowing/`) hold all deterministic logic (mypy-gated, engine-free); two thin `cli/` modules orchestrate the engines with function-local imports (mirroring `cli/pronounce.py`); additive edits to `store/`, `srs/`, `config/`, and `cli/main.py`. This keeps each engine in exactly one wrapper file (Principle V) and every deterministic unit independently testable and type-checked.

## Complexity Tracking

> No constitution violations. No entry required.

The only structural change to existing behavior is the behavior-preserving extraction of `srs.schedule.advance(...)` (justified above and pinned green by existing `srs` tests). Everything else is purely additive (new modules, new commands, default-empty store section, one optional config key).
