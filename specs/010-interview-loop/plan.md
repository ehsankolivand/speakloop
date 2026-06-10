# Implementation Plan: Interview Loop

**Branch**: `010-interview-loop` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-interview-loop/spec.md`

## Summary

Turn SpeakLoop's isolated, monologue practice session into an adaptive daily loop —
**due-question selection → warm-up drill → question + 3 attempts → 1–2 spoken follow-ups →
report** — and harden the feedback pipeline against wrong feedback. Five prioritized, independently
shippable slices: interactive follow-ups (P1), cross-session memory + spaced repetition + warm-up
(P2), content-coverage scoring (P3), trustworthy triage (P4), and behavioral/hypothetical question
types (P5).

**Technical approach**: a pure **extension** of the existing architecture, not a rewrite. Every new
language-model step (follow-up generation, key-point extraction, coverage scoring, content-error
detection, mishearing triage, artifact consistency check, drill generation) is a new caller of the
**existing `LLMEngine` Protocol** behind the existing `--cloud` routing — no new engine client code
(Principle V). All spoken output reuses the existing TTS path; all recording/transcription reuses the
existing ASR path. Session Markdown files with YAML frontmatter stay the single source of truth for
raw per-session data (additive optional keys, `schema_version` stays **1**). One **new derived store**
— a versioned JSON file, fully rebuildable from session files via `speakloop rebuild` — holds the
spaced-repetition schedule, the key-point cache, and cross-session pattern aggregation. Each new
language-model call gets an explicit JSON output schema, validation via the existing recovery ladder,
and graceful degradation (save raw audio + transcripts, mark analysis pending, never lose a recording).

## Technical Context

**Language/Version**: Python 3.12 (pinned `>=3.12,<3.13`, `pyproject.toml:7`); `uv` only.

**Primary Dependencies**: existing only — `typer`, `rich`, `pyyaml`, `python-frontmatter`, `numpy`,
`sounddevice`/`soundfile`, `kokoro-mlx` (TTS), `mlx-whisper` + `silero-vad` (ASR), `mlx-lm` (local LLM),
`json-repair` (LLM JSON recovery). **Zero new third-party dependencies** — the new store and content
hashing use stdlib `json` + `hashlib` (both already imported in `src/`); `sqlite3` is deliberately
not used (see research.md R4).

**Storage**:
- Raw session data → Markdown + YAML frontmatter in `data/sessions/YYYY-MM-DD-<qid>[-N].md` (unchanged
  location; `schema_version` stays 1, new keys additive-optional).
- Derived cross-session state → one new versioned JSON file under `~/.speakloop/` (the store), with its
  own `store_version`, rebuildable from session files.
- User-editable config (daily capacity, loop toggles) → YAML under `~/.speakloop/` (Constitution: user
  config is YAML).

**Testing**: `pytest` with existing markers (`unit`, `contract`, `integration`, `live_asr`, `live_llm`,
`live_cloud`). New language-model/ASR/TTS-touching tests use **cached fixtures** under `tests/fixtures/`
(no live model calls — Development Guidelines). The human-labeled `tests/fixtures/transcripts/gold_set.yaml`
is extended into the triage/coverage labeled validation set for SC-003/SC-004/SC-006.

**Target Platform**: Apple Silicon (M-series) macOS, CLI only (`rich`), offline-first.

**Project Type**: Single-project CLI (the existing `src/speakloop/` package).

**Performance Goals**: first follow-up question begins playing within **~10 s** of the final attempt
ending on a typical M-series laptop. Met by (a) warming the analysis model during the final attempt's
recording and (b) reusing the already-computed attempt-1/2 transcripts so only the attempt-3 transcript
is on the critical path (research.md R5). The ~10 s is a target, not a hard gate.

**Constraints**: offline-first (no network in the core loop except opt-in `--cloud` LLM calls); no
recording ever lost; English-only; CLI-only; `schema_version` stays 1; engine imports stay function-local
so `speakloop --help` loads no models.

**Scale/Scope**: a single user; a question bank of tens-to-hundreds of questions; tens-to-hundreds of
session files. The derived store is a few KB–tens of KB of JSON.

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

| Principle / Constraint | Status | How this feature complies |
|---|---|---|
| I. English-only UI | PASS | All new prompts, reports, drill/follow-up text are English. |
| II. Offline-first | PASS | No new network calls. New LLM steps route through the **existing** local-by-default / opt-in `--cloud` layer; the core loop is offline when local. |
| III. Privacy by design | PASS | The new store and all new data stay on disk under `~/.speakloop/` and `data/sessions/`. `--cloud` sends the same data category as today, with the same disclosure. |
| IV. Modular by design (NON-NEGOTIABLE) | PASS | Each new concern is its own single-responsibility module with its own `CLAUDE.md`: `interviewer/`, `triage/`, `coverage/`, `srs/`, `warmup/`, `store/`. Cross-session reads still extend `trends/`. |
| V. Swappable engines | PASS | **No new engine client code.** Every new LLM call uses the injected `LLMEngine.generate(...)`; TTS via `KokoroEngine.synthesize`; ASR via the existing wrapper. No engine package is imported outside its one wrapper. |
| VI. Resumable downloads | N/A | No new models. |
| VII. Apple Silicon target | PASS | Latency budget measured on M-series; no platform assumptions beyond existing. |
| VIII. Easy install / `--help` offline | PASS | New CLI commands (`today`, `rebuild`, `resume`) and the new LLM runners use function-local engine imports inside `cli/practice.py` build closures, like today; `--help` loads no engines. |
| IX. Obsidian reports / stable schema | PASS | Reports stay Markdown+YAML in `data/sessions/`; all new frontmatter keys are additive-optional; `schema_version` stays 1 (research.md R7); old reports parse unchanged (SC-012). |
| X. Research in repo | PASS | No engine change → no `doc/research_*.md` change required. The SRS/triage/versioning decisions live in this feature's `research.md`. |
| XI. AI-collaborator friendly | PASS | Six small loadable modules, each with a `CLAUDE.md`; no widening of any existing module's context surface beyond additive fields. |
| XII. Iterative delivery | PASS | Ships as the 5 prioritized slices; each is independently usable (spec "Slice independence & sequencing" + cross-slice fallbacks FR-004/FR-010/FR-016). |
| Python 3.12 / `uv` | PASS | Unchanged. |
| User config = YAML | PASS | Loop config is YAML; the derived store is an **internal cache** (not user config) and may be JSON (FR-040). |
| Stable report schema (versioned, bump = migration) | PASS | Additive-optional only → no bump; version-aware parse retained for a future breaking change (research.md R7). |
| Engine tests use cached fixtures | PASS | New LLM/ASR/TTS tests stub the Protocol or use cached WAV/JSON fixtures. |

**Result**: PASS. No violations → **Complexity Tracking is empty** (no deviations to justify).

## Project Structure

### Documentation (this feature)

```text
specs/010-interview-loop/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions R1..R9
├── data-model.md        # Phase 1 — entities, frontmatter additions, store schema
├── quickstart.md        # Phase 1 — how to run the daily loop + new commands
├── contracts/           # Phase 1 — JSON I/O schemas for each new LLM call + CLI + store
│   ├── llm-calls.md             # C1–C6: followups, keypoints, coverage+content-errors, mishearing, consistency, drill
│   ├── store-schema.md          # the versioned JSON derived store + rebuild contract
│   ├── frontmatter-additions.md # additive optional report keys (schema_version stays 1)
│   └── cli-commands.md          # practice (loop), today, trends (stats), rebuild, resume, doctor
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
src/speakloop/
├── cli/                     # MODIFY: practice.py (due-selection, warm-up, follow-ups, build all LLM
│   │                        #   runners over one engine, --no-warmup/--no-followups); main.py (register
│   │                        #   today, rebuild, resume; per-pattern trends via trends); doctor.py rows;
│   │                        #   NEW today.py, rebuild.py, resume.py thin delegates
│   ├── practice.py
│   ├── main.py
│   ├── doctor.py
│   ├── today.py             # NEW
│   ├── rebuild.py           # NEW
│   └── resume.py            # NEW
├── interviewer/             # NEW MODULE (P1) — follow-up generation + probe-worthiness gate + CLAUDE.md
│   ├── __init__.py
│   ├── followups.py         #   generate_followups(question, transcripts, *, llm, system_prompt) -> list[FollowUp]
│   ├── followups_prompt_default.txt
│   └── CLAUDE.md
├── triage/                  # NEW MODULE (P4) — span triage + artifact consistency check + CLAUDE.md
│   ├── __init__.py
│   ├── hallucination.py     #   deterministic: VAD gaps + no_speech_prob/avg_logprob/compression + phantom list
│   ├── phantom_phrases.txt  #   known ASR phantom phrases (data file, like common_words.txt)
│   ├── mishearing.py        #   LLM-assisted pronunciation-flag classification (when LLM available)
│   ├── consistency.py       #   verify generated artifact vs ideal answer (FR-027)
│   ├── triage_prompt_default.txt
│   └── CLAUDE.md
├── coverage/                # NEW MODULE (P3) — key points + coverage + content errors + CLAUDE.md
│   ├── __init__.py
│   ├── keypoints.py         #   derive_key_points(question, *, llm) -> KeyPointSet (hash-versioned)
│   ├── scoring.py           #   score_coverage(key_points, transcript, *, llm) -> CoverageRecord
│   ├── content_errors.py    #   find_content_errors(key_points/ideal, transcript, *, llm) -> list[ContentError]
│   ├── keypoints_prompt_default.txt
│   ├── coverage_prompt_default.txt
│   └── CLAUDE.md
├── srs/                     # NEW MODULE (P2b) — grade + interval ladder + mastery + due-queue + CLAUDE.md
│   ├── __init__.py
│   ├── grade.py             #   grade_session(coverage, content_errors, grammar, fluency) -> Grade
│   ├── schedule.py          #   next_due(entry, grade, *, today) ; mastery rule ; interval ladder
│   ├── queue.py             #   due_queue(store, *, today, capacity) -> list[DueItem] (priority order)
│   └── CLAUDE.md
├── warmup/                  # NEW MODULE (P2c) — drill generation + deterministic pass/fail + CLAUDE.md
│   ├── __init__.py
│   ├── drill.py             #   generate_drill(top_error, *, llm, system_prompt) -> Drill ; judge_item(...)
│   ├── drill_prompt_default.txt
│   └── CLAUDE.md
├── store/                   # NEW MODULE (P2a) — versioned JSON derived store + rebuild + CLAUDE.md
│   ├── __init__.py
│   ├── model.py             #   Store dataclasses + store_version
│   ├── io.py                #   load(path) / save_atomic(path, store) (stdlib json, os.replace)
│   ├── rebuild.py           #   rebuild(sessions_dir) -> Store (fold session files)
│   └── CLAUDE.md
├── asr/                     # MODIFY: surface per-segment metadata (avg_logprob, no_speech_prob,
│   │                        #   compression_ratio) + VAD regions on Transcript (additive optional,
│   │                        #   defaulted for frozen dataclass / Parakeet path). NO engine swap.
│   ├── interface.py         #   Transcript += segments / vad_regions (optional, default ())
│   └── whisper_mlx_engine.py#   _result_to_transcript surfaces the discarded signals
├── metrics/                 # MODIFY: compute_all(transcript, *, vad_regions=None) — real-speech-only
│   └── __init__.py          #   when regions present; identical to today when None (back-compat)
├── feedback/                # MODIFY: frontmatter.Session += type/warmup/follow_ups/coverage/
│   │                        #   content_errors/pronunciation_flags/answer_grade/key_points(+version)/
│   │                        #   analysis_pending (additive optional); report_builder new sections;
│   │                        #   keep schema_version 1
│   ├── frontmatter.py
│   └── report_builder.py
├── sessions/                # MODIFY: coordinator.py — warm-up before attempt 1, follow-ups after
│   │                        #   attempt 3, triage hook before grammar, coverage scoring per attempt,
│   │                        #   answer grade + schedule update + store write after report
│   └── coordinator.py
├── content/                 # MODIFY: schema.py — additive optional `type` field (default definition),
│   └── schema.py            #   loader accepts it; question-file schema_version NOT bumped
├── config/                  # MODIFY: paths.py — store path, loop-config path, new prompt-file paths
│   └── paths.py
└── trends/                  # MODIFY: aggregator.py / renderer.py — per-pattern occurrence time-series
    ├── aggregator.py        #   (the FR-009 "stats" view, extending the existing dashboard)
    └── renderer.py

tests/
├── unit/{interviewer,triage,coverage,srs,warmup,store}/   # NEW per-module unit tests (stubbed engines)
├── contract/                # NEW: JSON-schema validation tests for each new LLM call's parser
├── integration/             # NEW: daily-loop end-to-end (stubbed engines), rebuild round-trip,
│                            #   analysis-pending → resume, schema back-compat
└── fixtures/
    ├── transcripts/gold_set.yaml          # EXTEND: label hallucinations + mishearings + content errors
    ├── transcripts/triage/                # NEW: labeled triage cases (SC-003/SC-006)
    ├── coverage/                          # NEW: ideal-answer → key-point + coverage cases (SC-004/SC-009)
    └── store/                             # NEW: sample session sets → expected rebuilt store
```

**Structure Decision**: single-project extension of the existing `src/speakloop/` package. Six new
single-responsibility modules (each with its own `CLAUDE.md`, per Principle IV) carry the new concerns;
existing modules receive only additive, backward-compatible changes. No new top-level project, no new
runtime dependency.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.

## Phasing (maps to the spec's prioritized slices and Principle XII)

Each phase is independently shippable; later phases enrich earlier ones through the spec's documented
fallbacks (FR-004/FR-010/FR-016). `/speckit-tasks` will expand these into ordered tasks.

1. **Foundation** (shared, no user-facing slice alone): ASR segment/VAD surfacing; metrics real-speech
   param; `store/` + `rebuild`; frontmatter additive fields + report sections; generalize
   `cli/practice.py` to build all LLM runners over one engine.
2. **P1 — Interviewer** (`interviewer/`, coordinator follow-up stage, follow-up report section, latency warm-up).
3. **P2 — Memory/SRS/Warm-up** (`srs/`, `warmup/`, trends per-pattern series, `today` command, schedule
   write in coordinator). Uses grammar+fluency grade fallback until P3 lands.
4. **P3 — Coverage** (`coverage/`, per-attempt scoring, content errors, coverage report section; upgrades
   the answer-quality grade to coverage-primary).
5. **P4 — Trustworthy pipeline** (`triage/` hallucination filter pre-grammar, mishearing flags, artifact
   consistency check; metrics over real-speech spans).
6. **P5 — Question types** (`content/schema.py` `type`, STAR/conditional guidance in report, type-aware
   key points). Plus `resume` for analysis-pending sessions and `doctor` rows.
