---
description: "Task list for feature 015 — engine-aware onboarding"
---

# Tasks: Engine-Aware Onboarding

**Input**: Design documents in `specs/015-engine-aware-onboarding/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-commands.md, quickstart.md

**Tests**: INCLUDED. speakloop is test-gated (constitution dev guidelines; load-bearing gates
named in the root CLAUDE.md) and the sprint must hand back a tested branch — so every story
ships unit/integration tests. No test touches a live model, the real `claude` binary, the mic,
or the keyboard (`.claude/rules/testing.md`); injection/monkeypatch only.

**Organization**: by user story (P1 → P2 → P3), each independently testable. File paths are
exact. `[P]` = different file, no dependency on an incomplete task.

**Anti-rot rule**: each story's context-file task (updating the owning CLAUDE.md) lands in the
SAME commit as that story's behavior change (constitution v1.1.0). Every CLAUDE.md ≤200 lines
(`tests/integration/test_context_file_budget.py`).

---

## Phase 1: Setup

- [X] T001 Record the baseline full-suite result: run `uv run pytest -q` and note the pass/skip
  count for the before/after delta (SC-009). No source change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**No cross-story foundational code is required.** The shared primitives are scoped within US1
(the writer, the provisioning predicate, the readiness model — T002–T004) and are not needed by
US2 (questions) or US3 (docs). US1, US2, US3 are independent and may proceed in any order after
Setup. The autouse `_isolate_loop_config` fixture and `SPEAKLOOP_HOME` env give every new test
home isolation with no new fixture.

**Checkpoint**: proceed to user stories.

---

## Phase 3: User Story 1 — Choose & persist an engine, download only what it needs (Priority: P1) 🎯 MVP

**Goal**: Set the feedback engine once (persisted), provision exactly that engine's models
(cloud never fetches the large local LLM), and have `doctor` report engine-aware readiness.

**Independent Test**: `setup --engine openrouter` persists the choice and downloads only
TTS+ASR; `setup --engine local` also fetches the local LLM; `practice` with no flag uses the
persisted engine and an explicit flag overrides one run; `doctor` names the active engine and
does not false-fail on an unneeded model.

### Primitives (lowest layer — land first)

- [X] T002 [P] [US1] Add `save_engine(engine) -> Path` to `src/speakloop/config/loop_config.py`:
  validate `engine ∈ VALID_ENGINES` (else `ValueError`); read existing `loop.yaml` (absent/
  malformed → `{}`); set `engine`; `yaml.safe_dump(sort_keys=False)`; `mkdir` parent; return path.
- [X] T003 [P] [US1] Add `engine_needs_local_llm(engine, *, listen_only) -> bool`
  (`engine == "local" and not listen_only`) to `src/speakloop/installer/__init__.py` and export it
  in `__all__`.
- [X] T004 [US1] Add `src/speakloop/cli/engine_status.py`: `active_engine()` (reads
  `loop_config.load().engine`), `Requirement` + `EngineReadiness` dataclasses, and
  `engine_readiness(engine) -> EngineReadiness` with function-local imports of
  `installer.{manifest,validator}`, `llm.openrouter_credentials`,
  `llm.claude_code_engine.doctor_probe` (no engine package import).

### Command layer

- [X] T005 [US1] Add `src/speakloop/cli/setup.py` `run(*, engine=None, no_download=False,
  input_fn=input, console=None)`: resolve engine (explicit → interactive numbered prompt
  defaulting to current → non-interactive keep-current); persist via `loop_config.save_engine`;
  unless `no_download`, `installer.ensure_models("B")` then `ensure_models("C")` only when
  `engine == "local"`; report cloud-credential readiness (no network); print the
  `engine_status` readiness summary. Invalid engine → `typer.Exit(2)`.
- [X] T006 [US1] Register `setup` in `src/speakloop/cli/main.py` (`--engine`, `--no-download`),
  delegating to `cli/setup.py`; clarify `--cloud`/`--engine` help text on `practice`/`resume` so
  the alias relationship is explicit (FR-004). Keep the local import pattern (no engine touch).
- [X] T007 [US1] Engine-aware provisioning in `src/speakloop/cli/practice.py`: keep the required
  base `ensure_models("A" if listen_only else "B")` (decline → exit, unchanged); then, when
  `installer.engine_needs_local_llm(engine_choice, listen_only=listen_only)` and the local model
  is absent, call `ensure_models("C")` wrapped so `InstallDeclinedError`/`InstallFailedError`
  prints one English notice and continues (degrade, no exit). Place before the grammar-analyzer build.
- [X] T008 [US1] Engine-aware `src/speakloop/cli/doctor.py`: in `_models()` make the
  `required_for_phase == "C"` row FAIL-on-absence only when `engine_status.active_engine() ==
  "local"`, else a non-failing "not required for the active engine (<engine>)" row (keep all rows
  rendered; keep a `speakloop practice` remediation substring on a FAIL row). Add a
  `_feedback_engine()` section from `engine_status` (active engine + readiness + next step;
  cloud/claude rows non-failing) and include it in `_collect()`.

### Tests (US1)

- [X] T009 [P] [US1] `tests/unit/config/test_loop_config_save.py`: round-trip (`save_engine` then
  `load().engine`), preserves a pre-existing unrelated key, rejects an invalid value.
- [X] T010 [P] [US1] `tests/unit/installer/test_engine_provisioning.py`: truth table for
  `engine_needs_local_llm` across {local,openrouter,claude} × {listen_only True/False}.
- [X] T011 [P] [US1] `tests/unit/cli/test_engine_status.py`: `engine_readiness` per engine with
  monkeypatched validator/credentials/`doctor_probe`; cloud requirements are `optional=True`.
- [X] T012 [P] [US1] `tests/unit/cli/test_setup.py`: monkeypatch `installer.ensure_models` to
  record phases; assert openrouter→{"B"}, claude→{"B"}, local→{"B","C"}; `--no-download`→no
  ensure calls; persistence written to the isolated `loop_config_path()`; non-interactive keeps
  current; invalid engine → exit 2. Set `SPEAKLOOP_HOME` to tmp; inject `input_fn`.
- [X] T013 [US1] Extend `tests/unit/cli/test_doctor.py`: with a cloud `engine:` written to the
  isolated loop config, a missing local LLM does NOT FAIL and the active engine is named; keep
  the existing local-default FAIL cases green.
- [X] T014 [P] [US1] `tests/integration/test_setup_flow.py`: fresh-clone sim — `setup openrouter`
  triggers no `ensure_models("C")`; `setup local` does; after setup, `resolve_engine_choice(None,
  False)` returns the persisted engine.
- [X] T015 [P] [US1] `tests/integration/test_practice_engine_aware_download.py`: `practice` with a
  cloud engine never calls `ensure_models("C")`; with local + missing LLM + declined download, the
  run degrades (no `Exit`) and proceeds. Use injected `tts_engine`/`play_fn` + monkeypatched
  `ensure_models` per existing practice-test patterns.

### Context (anti-rot — same commit as T002–T008)

- [X] T016 [US1] Update owning context files: `src/speakloop/config/CLAUDE.md` (`save_engine` +
  explicit-only-write note), `src/speakloop/installer/CLAUDE.md` (`engine_needs_local_llm`),
  `src/speakloop/cli/CLAUDE.md` (setup command, engine_status, engine-aware doctor section,
  practice provisioning), and root `CLAUDE.md` (Commands list + module-table notes). All ≤200 lines.

**Checkpoint**: US1 fully functional and independently testable (the MVP).

---

## Phase 4: User Story 2 — Add & validate your own questions (Priority: P2)

**Goal**: A template, a validator with precise errors, and a precedence/where view — reusing the
existing loader/schema; nothing auto-created in home.

**Independent Test**: `questions template` emits a file that `questions validate` accepts; a broken
file is rejected naming the entry+field; `questions where` shows the precedence and active file.

- [X] T017 [P] [US2] Add `src/speakloop/content/template.py` `template_text() -> str`: a
  `schema_version: 1` commented starter with 2–3 entries across `definition`/`behavioral`/
  `hypothetical` showing `tags`/`difficulty`/`voice_override`. Must pass `content.load()` unedited.
- [X] T018 [US2] Add `src/speakloop/cli/questions.py`: `validate(path=None)` (explicit arg else
  `paths.resolve_qa_file()`; `content.load()` → success summary + warnings exit 0, else precise
  error exit 1; no file → precedence hint exit 1); `template()` (print `template_text()` to stdout,
  no writes); `where()` (print precedence + active file + count).
- [X] T019 [US2] Register a `questions` typer sub-app (`validate`/`template`/`where`) in
  `src/speakloop/cli/main.py` via `app.add_typer(...)`, delegating to `cli/questions.py`.

### Tests (US2)

- [X] T020 [P] [US2] `tests/unit/content/test_question_template.py`: `content.load(<temp file of
  template_text()>)` returns a `QAFile` with ≥2 questions, zero schema errors, and the expected types.
- [X] T021 [P] [US2] `tests/unit/cli/test_questions.py` (CliRunner): valid fixture → exit 0 + count;
  invalid fixture → exit 1 + entry id + field in output; `template` stdout round-trips through
  `content.load()`; `where` prints the three precedence locations and the active file.

### Context (anti-rot — same commit as T017–T019)

- [X] T022 [US2] Update `src/speakloop/content/CLAUDE.md` (template source of truth) and
  `src/speakloop/cli/CLAUDE.md` (questions group) + root `CLAUDE.md` Commands. All ≤200 lines.

**Checkpoint**: US1 and US2 both work independently.

---

## Phase 5: User Story 3 — Onboarding docs match the flow (Priority: P3)

**Goal**: README/quickstart describe the real, shipped engine-aware setup + question management.

**Independent Test**: a reader follows the README per engine and to add a question set with no step
that contradicts behavior.

- [ ] T023 [US3] Update `README.md`: add an engine-aware setup section (clone → `speakloop setup
  --engine <X>` → session; what each engine downloads/needs), document persistence + the
  `--cloud`/`--engine` relationship, and a question-management section (`questions template`/
  `validate`/`where`). Reconcile the existing Cloud-mode and "Use your own question set" sections.
- [ ] T024 [US3] Cross-check every command/flag in `README.md` against `quickstart.md` and the
  implemented surface; fix any stale or contradicting line.

**Checkpoint**: all three stories functional; docs accurate.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T025 Run the full suite `uv run pytest`; confirm pass count ≥ baseline (T001) and the gates
  green: `test_help_without_models`, `test_path_portability_audit`, `test_context_file_budget`,
  `test_analysis_equivalence`.
- [ ] T026 [P] Re-run isolation gates explicitly: `uv run pytest
  tests/integration/test_help_without_models.py tests/unit/asr/test_engine_import_isolation.py`
  to prove the new commands load no engine package.
- [ ] T027 [P] `ruff check` the changed files (advisory; pre-existing findings are not a gate) and
  do a manual `quickstart.md` smoke: `--help`, `setup --help`, `questions --help`,
  `questions template | uv run speakloop questions validate -` (or via a temp file).
- [ ] T028 Confirm no personal absolute path in any new file and every CLAUDE.md ≤200 lines; final
  read-through of the four touched module CLAUDE.md files + root for accuracy.

---

## Dependencies & Execution Order

- **Setup (T001)**: first (baseline measurement).
- **US1 (T002–T016)**: primitives T002–T004 before command layer T005–T008; T004 (engine_status)
  before T005/T008; tests T009–T015 after their targets; T016 in the same commit(s) as T002–T008.
- **US2 (T017–T022)**: T017 before T018; T018 before T019; tests after; T022 same commit as code.
- **US3 (T023–T024)**: after US1+US2 exist so docs describe real behavior.
- **Polish (T025–T028)**: last.

### Story independence
- US1, US2, US3 touch disjoint code except `cli/main.py` (registration) and root `CLAUDE.md`
  (Commands) — coordinate those two shared files when landing stories in parallel.

### Parallel opportunities
- T002 and T003 are `[P]` (different files). US1 tests T009–T012, T014–T015 are `[P]`.
- US2 T020–T021 are `[P]`. US1 and US2 are independent and can proceed concurrently.

## Implementation Strategy

1. **MVP = US1**: Setup → US1 → validate (`setup`/`practice`/`doctor` engine-aware) → commit.
2. **+US2**: questions template/validate/where → validate → commit.
3. **+US3**: README → validate against quickstart → commit.
4. **Polish**: full suite + gates + budgets → final commit.

Commit boundaries: one Conventional Commit per story (code + tests + owning CLAUDE.md together),
then a docs commit (US3), then a polish/verification commit. Push the feature branch only.
