# Implementation Plan: Engine-Aware Onboarding

**Branch**: `015-engine-aware-onboarding` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/015-engine-aware-onboarding/spec.md`

## Summary

Make a fresh clone reach a working practice session fast and keep day-to-day use
flag-free, without touching analysis quality, prompts, the report schema, or
offline-by-default. Three slices:

- **P1** — a new `setup` command persists the chosen feedback engine to the existing
  `loop.yaml` `engine:` key and provisions **only** the models that engine needs (speech
  + transcription always; the large local feedback LLM only for the `local` engine). The
  same engine-aware rule is applied inside `practice`, and `doctor` gains an active-engine
  readiness view that stops false-failing on a local model a cloud user does not need.
- **P2** — a `questions` command group: `validate` (precise errors via the existing
  loader/schema), `template` (a canonical, schema-valid commented starter emitted to
  stdout — never written to home), and `where` (precedence + active file).
- **P3** — README/quickstart rewrite so a cloner can follow it per-engine end to end.

The persistence key (`engine:`) and the resolution precedence (`--engine` → `loop.yaml`
→ `local`) already exist (`config/loop_config.py`, `cli/practice.py:resolve_engine_choice`).
The new work is a *writer* for that key, an engine→model provisioning predicate, the
`setup`/`questions` commands, an engine-aware `doctor`, and docs — all additive.

## Technical Context

**Language/Version**: Python 3.12 (pinned `>=3.12,<3.13`).

**Primary Dependencies**: `typer` (CLI), `rich` (console), `pyyaml` (config + question
files), `huggingface_hub` (resumable download, reused via `installer`). No new dependency.

**Storage**: User config + credentials under `~/.speakloop/` (YAML + token file);
models under `~/.speakloop/models/`; questions in-repo `content/questions.yaml` or the
personal `~/.speakloop/qa.yaml`. The persisted engine is the existing optional
`loop.yaml engine:` key.

**Testing**: `pytest` (unit / integration / contract markers). Engine packages and the
real `claude` binary are never touched by tests (`.claude/rules/testing.md`); fakes/injection
only. Reuse the autouse `_isolate_loop_config` fixture (points `loop_config_path()` at a
temp file) and `SPEAKLOOP_HOME` env for home isolation.

**Target Platform**: macOS Apple Silicon (primary), CLI only.

**Project Type**: Single-project CLI (the 19-module `src/speakloop/` layout).

**Performance Goals**: `speakloop --help` and all new commands start with no models present
and load none of the five engine packages (`mlx_whisper`, `silero_vad`, `parakeet_mlx`,
`mlx_lm`, `kokoro_mlx`) at import. No latency-sensitive paths added.

**Constraints**: Offline-by-default after model download (constitution II); YAML-only user
config; no GUI; no `pip install` workflow; report `schema_version` stays 1; every CLAUDE.md
≤200 lines; no personal absolute paths in committed files.

**Scale/Scope**: ~4 new source files + 5 changed source files + 5 context files (root +
config/installer/cli/content CLAUDE.md) + README + a focused test set. No data migration.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.1.0. Re-checked post-design.*

| Principle / Constraint | Verdict | How this feature complies |
|---|---|---|
| I. English-Only UI | PASS | Every new string (setup, questions, doctor rows, README) is English. |
| II. Offline-First | PASS | No new network on the default local path. `setup` credential checks are local: `resolve_token()` (file/env read) and `claude` `doctor_probe()` (credit-free local subprocess, already used by doctor). All downloads go through the existing `installer` (the sanctioned HF exception). Deep cloud-token network validation stays on the existing opt-in `practice --cloud` first-run path. |
| III. Privacy by Design | PASS | No file is uploaded/mirrored. Cloud use stays the existing opt-in transcript-only path; this feature adds none. |
| IV. Modular by Design | PASS | New files are single-responsibility (`cli/setup.py`, `cli/questions.py`, `cli/engine_status.py`, `content/template.py`); each touched module's CLAUDE.md is updated in the same commit. |
| V. Swappable Engines | PASS | No engine-specific import leaks. New modules import only `installer` (manifest/validator), `config`, `llm.openrouter_credentials`, and `llm.claude_code_engine.doctor_probe` — none are the five engine packages. Isolation gates (`test_help_without_models`, `test_engine_import_isolation`) stay green. |
| VI. Resumable Downloads | PASS | Provisioning reuses `installer.ensure_models` (aria2c/`snapshot_download(resume_download=True)`); nothing already present is re-fetched. |
| VII. Apple Silicon | PASS | No platform assumptions changed. |
| VIII. Easy Install | PASS | This is the principle the feature most advances: clone → `setup` → working session, with size disclosure + consent reused. `--help` and new commands stay model-free. |
| IX. Obsidian Reports | PASS | No report changes; `schema_version` untouched. |
| X. Research in Repo | PASS (N/A) | No engine or methodology change, so no `doc/research_{tts,asr,llm,methodology}.md` update is required. Feature design rationale lives in `specs/015/research.md`. |
| XI. AI-Collaborator Friendly | PASS | Anti-rot CLAUDE.md updates in the same commits; modules stay small and loadable; line-budget gate honored. |
| XII. Iterative Delivery | PASS | P1/P2/P3 are independently shippable; the local-feedback-model decline degrades to a recorded, resumable session (partial system stays usable). |
| Non-negotiables (uv, YAML config, model dir, CLI-only, MIT, no new external services) | PASS | Reuses the `engine:` YAML key (no new format/file type); no GUI; no `pip` workflow; no new external service. |
| Dev guidelines (Conventional Commits, stable schema, anti-rot same-commit) | PASS | Conventional Commits; no schema bump; owning context file updated per behavior-changing commit. |

**Result**: No violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/015-engine-aware-onboarding/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 — design decisions
├── data-model.md        # Phase 1 — entities (config key, requirement profile, template)
├── quickstart.md        # Phase 1 — per-engine onboarding walkthrough
├── contracts/
│   └── cli-commands.md   # Phase 1 — command/flag/exit-code contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 — /speckit-tasks output
```

### Source Code (repository root)

```text
src/speakloop/
├── config/
│   ├── loop_config.py        # CHANGE: add save_engine() writer (read-modify-write loop.yaml)
│   └── CLAUDE.md             # CHANGE: document the writer + explicit-only write invariant
├── installer/
│   ├── __init__.py           # CHANGE: add engine_needs_local_llm() provisioning predicate
│   └── CLAUDE.md             # CHANGE: document engine-aware provisioning predicate
├── content/
│   ├── template.py           # NEW: canonical schema-valid commented question template
│   └── CLAUDE.md             # CHANGE: document the template source of truth
└── cli/
    ├── main.py               # CHANGE: register `setup` + `questions` sub-app
    ├── setup.py              # NEW: persist engine + engine-aware provisioning + readiness
    ├── questions.py          # NEW: validate / template / where
    ├── engine_status.py      # NEW: shared active-engine readiness (doctor + setup)
    ├── practice.py           # CHANGE: engine-aware local-LLM provisioning (graceful)
    ├── doctor.py             # CHANGE: engine-aware model readiness + active-engine section
    └── CLAUDE.md             # CHANGE: document new commands + doctor section + practice change

CLAUDE.md                     # CHANGE: Commands table, SPECKIT block (015 active), module table
README.md                     # CHANGE (P3): engine setup/persistence + question management

tests/
├── unit/
│   ├── config/test_loop_config_save.py       # NEW
│   ├── installer/test_engine_provisioning.py # NEW
│   ├── content/test_question_template.py     # NEW
│   └── cli/
│       ├── test_setup.py                     # NEW
│       ├── test_questions.py                 # NEW
│       ├── test_engine_status.py             # NEW
│       └── test_doctor.py                    # CHANGE: engine-aware cases (additive)
└── integration/
    ├── test_setup_flow.py                    # NEW: cloud→no Phase C, local→Phase C
    └── test_practice_engine_aware_download.py# NEW: practice provisioning by engine
```

**Structure Decision**: Single-project CLI; all changes live under the existing
`src/speakloop/{config,installer,content,cli}` modules. No new top-level module is created —
the new CLI files belong to the existing `cli` module (its CLAUDE.md is updated), keeping the
19-module map intact (constitution IV).

## Design Notes (per slice)

### P1 — engine choice, persistence, provisioning, doctor

1. **`config/loop_config.save_engine(engine) -> Path`** — validates `engine ∈ VALID_ENGINES`,
   read-modify-writes `loop.yaml` preserving any existing keys (`yaml.safe_dump(sort_keys=False)`),
   creates the parent dir. Called **only** by `setup` (FR-005). Malformed existing file → start
   from `{}` (consistent with `load()`'s tolerance).
2. **`installer.engine_needs_local_llm(engine, *, listen_only) -> bool`** = `engine == "local"
   and not listen_only`. The single source of truth for "does this run need Phase C." Pure;
   exported in `__all__`.
3. **`practice.run`** — keep the required base `ensure_models("A" if listen_only else "B")`
   (decline → exit, unchanged). Then, if `engine_needs_local_llm(engine_choice,
   listen_only=...)` and the local feedback model is missing, call `ensure_models("C")` with a
   **graceful** wrapper: `InstallDeclinedError`/`InstallFailedError` → one English notice and
   continue (no exit). `_build_grammar_analyzer` already returns `None` when the model is
   absent → recorded, resumable session (FR-009). Placed before the grammar-analyzer build so a
   just-downloaded model is picked up.
4. **`cli/setup.py`** — resolve engine (explicit `--engine` → interactive numbered prompt
   defaulting to the current persisted engine → non-interactive keep-current); persist via
   `save_engine`; unless `--no-download`, ensure base `"B"` always and `"C"` for `local`; report
   cloud credential readiness (no network) and print a readiness summary via `engine_status`.
   `input_fn` injectable; uses module-level `installer.ensure_models` (test-patchable).
5. **`cli/engine_status.py`** — `active_engine()` and `engine_readiness(engine) -> EngineReadiness`
   (a `Requirement` list + overall `ready`). Imports `installer.{manifest,validator}`,
   `llm.openrouter_credentials`, `llm.claude_code_engine.doctor_probe` function-locally.
6. **`cli/doctor.py`** — `_models()` makes the Phase-C (local feedback) row engine-aware:
   FAIL-on-missing only when `active_engine()=="local"`, else a non-failing "not required for
   active engine" row; TTS/ASR rows keep FAIL-on-missing; all rows still render. A new
   `_feedback_engine()` section (from `engine_status`) names the active engine + readiness +
   next steps (cloud rows non-failing, matching the opt-in convention). A FAIL model
   remediation retains the substring `speakloop practice` (keeps `test_missing_model_fails`).

### P2 — questions

7. **`content/template.py`** — `template_text() -> str` returning a commented, multi-entry,
   schema-valid YAML (definition/behavioral/hypothetical, with `tags`/`difficulty`/
   `voice_override` shown). It must pass `content.load()` unedited (SC-006).
8. **`cli/questions.py`** — `validate(path)` resolves explicit arg else
   `paths.resolve_qa_file()`; `content.load()` → success summary (count + warnings, exit 0) or
   the loader's precise error (exit 1); `template()` prints `template_text()` to stdout (no
   writes); `where()` prints the precedence chain + active file (+ count if loadable).
9. **`cli/main.py`** — `questions` typer sub-app with `validate`/`template`/`where`; `setup`
   command; clarified `--cloud`/`--engine` help.

### P3 — docs

10. **README.md** — add an engine-aware setup section (clone → `setup <engine>` → session),
    document persistence + `--cloud`/`--engine`, and a question-management section
    (`questions template`/`validate`/`where`) consistent with the implemented surface.

## Phase 0 / Phase 1 outputs

- `research.md` — decisions D1–D10 (command shape, persistence write strategy, graceful decline,
  doctor engine-awareness, template-as-stdout, credential handling, test seams).
- `data-model.md` — the `engine:` key, the engine→requirement mapping, the template entity,
  the readiness model.
- `contracts/cli-commands.md` — `setup`, `questions {validate,template,where}`, the engine-aware
  `doctor` additions, and the `practice` provisioning contract (inputs, outputs, exit codes).
- `quickstart.md` — per-engine onboarding walkthrough used to validate P3.
