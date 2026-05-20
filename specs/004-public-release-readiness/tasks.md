---
description: "Task list for Public Release Readiness"
---

# Tasks: Public Release Readiness

**Input**: Design documents from `specs/004-public-release-readiness/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included where a test *is* the deliverable (US3 audit) or where the
question-file migration would otherwise break the existing suite (FR-005). Not added
speculatively elsewhere.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All paths are repo-relative to the repository root

## Path Conventions

Single project: `src/speakloop/`, `tests/`, plus repo-root `content/`, `README.md`,
`LICENSE`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Put the migrated default question file and license in place.

- [X] T001 [P] Migrate the question set verbatim from `src/speakloop/content/starter.yaml` to new repo-root file `content/questions.yaml`, preserving `schema_version: 1`, all four questions, and byte-for-byte field fidelity (FR-004)
- [X] T002 [P] Verify `LICENSE` at repo root is MIT and matches the constitution's mandated license; no edit expected (FR-025 / SC-E)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The question-file resolution backbone that both US1 (load default) and
US4 (load override) build on, plus keeping the existing suite green after the move.

**⚠️ CRITICAL**: US1 and US4 cannot be completed until this phase is done.

- [X] T003 Add `default_qa_file()` (returns `<cwd>/content/questions.yaml`) and `resolve_qa_file() -> Path | None` (precedence: `--qa-file` override → `~/.speakloop/qa.yaml` if it exists → `content/questions.yaml` if it exists → `None`) to `src/speakloop/config/paths.py`; preserve `qa_file_path()` / `set_qa_file_path()` semantics for the override path (FR-002, FR-003; contracts/question-resolution.md)
- [X] T004 In `src/speakloop/cli/practice.py`, replace `_ensure_starter_qa` (the copy-on-first-run) with a new helper `_resolve_qa_file(console) -> Path` that calls `paths.resolve_qa_file()` (name mirrors `paths.resolve_qa_file()`); on `None`, it prints one English message naming both `content/questions.yaml` and `~/.speakloop/qa.yaml` and `raise typer.Exit(1)` (FR-006); update the call site in `run()` accordingly and remove the auto-copy and the `importlib.resources` starter read
- [X] T005 In `src/speakloop/cli/main.py`, update the `--qa-file` help text to state the new default `content/questions.yaml` and the `~/.speakloop/qa.yaml` override (depends on T003)
- [X] T006 Remove the now-unused packaged resource `src/speakloop/content/starter.yaml` (single source of truth = `content/questions.yaml`) (depends on T001, T004)
- [X] T007 Update tests coupled to the packaged `starter.yaml` and/or the removed first-run auto-copy so the suite stays green (FR-005; documented migration) (depends on T001, T006):
  - `tests/conftest.py` — point the first-question fixture (`starter_question_id`) read at repo-root `content/questions.yaml` instead of the packaged resource.
  - `tests/integration/repro_gate_test.py` — same resource-read migration.
  - `tests/integration/test_offline_after_install.py` — same resource-read migration.
  - `tests/integration/test_phase_a_listen.py` — this test relies on the removed auto-copy: it points `SPEAKLOOP_QA_FILE` at a not-yet-existing tmp `qa.yaml` and asserts `qa_file.exists()` (line 71) after the run, which only held because `_ensure_starter_qa` copied the starter on first run. **Decision: keep using the robust `starter_question_id` fixture (already first-question-agnostic), pre-populate the tmp `qa.yaml` from `content/questions.yaml` before invoking, and drop the `qa_file.exists()` post-condition** (the cosmetic `"Explain how Kotlin"` branch in `StubTTS` is harmless and may stay). Note: there is no `kotlin-coroutines-basics` question id in the set (ids are `activity-*` / `onpause-*` / `onstop-*`), so no id-retention check is needed.

**Checkpoint**: `uv run pytest` passes against the relocated default; question resolution works for both default and override.

---

## Phase 3: User Story 1 - Clone, install, and finish a first session (Priority: P1) 🎯 MVP

**Goal**: A stranger reading only the root README installs on a fresh Apple Silicon
machine, finds the questions in-repo, and reaches a saved session report.

**Independent Test**: On a non-maintainer machine, follow only the README to install,
locate `content/questions.yaml`, and run one session to a completed report — without
reading source.

- [X] T008 [US1] Rewrite `README.md` opening: value proposition (who/why before tech, FR-013), supported platforms + v1 status (macOS Apple Silicon, Python 3.12; FR-014), install steps (`git clone` → `uv sync`; FR-015), and an end-to-end quickstart from clone to first completed report (FR-015, mirrors quickstart.md); plain Markdown only (FR-012)
- [X] T009 [US1] Add the annotated generic session-report example to `README.md` showing a top-level `asr:` provenance block, ≥1 grammar pattern, and the `top_priority` line — no real recording/name/maintainer data (FR-016, FR-017) (depends on T008)
- [X] T010 [US1] Add to `README.md`: where reports are saved (`data/sessions/`) and where questions live (`content/questions.yaml`), plus contributor links to the constitution and `specs/` (FR-018, FR-019) (depends on T008)
- [X] T011 [P] [US1] Update `src/speakloop/content/CLAUDE.md`, `src/speakloop/config/CLAUDE.md`, and the top-level `CLAUDE.md` module-map row to state `content/questions.yaml` as the default and `~/.speakloop/qa.yaml` as the override (drop "copied to ~/.speakloop/qa.yaml on first run") (FR-026)
- [X] T012 [US1] Add an integration test in `tests/integration/test_default_questions_inrepo.py` asserting that, with no `--qa-file` and no `~/.speakloop/qa.yaml`, the practice flow resolves and loads `content/questions.yaml` (acceptance scenarios 1–2)

**Checkpoint**: US1 is independently demoable — clone → README → finished report. MVP complete.

---

## Phase 4: User Story 2 - Recover from a rough edge without help (Priority: P2)

**Goal**: A user hitting a known rough edge finds the symptom in the README, reads the
cause, and applies the fix (or learns it is a known v1 limitation).

**Independent Test**: For each documented failure mode, confirm its entry names the
cause and gives either a concrete local fix or an explicit "known v1 limitation".

- [X] T013 [US2] Add a "Known limitations" section to `README.md`, placed *before* troubleshooting: states v1; accented technical jargon can be misheard despite biasing; LLM feedback can fail and degrade to fluency-only; audio replay exists while full pronunciation feedback does not (FR-021) (depends on T008)
- [X] T014 [US2] Add a "Troubleshooting" section to `README.md` with scannable entries (prominent symptom · one-line cause · single short-paragraph fix), covering at minimum: model-download failure (resume + proxy/network-restricted note); LLM feedback degraded to fluency-only (names the `phase_c_error` report field and what each cause means); misheard technical terms (per-session `initial_prompt` biasing + how to add domain terms; known v1 limitation); `silero-vad` version conflict (why pinned + recover via `uv sync` to the pinned version); macOS microphone permission on first run; recording-loop hang at final attempt (interim Ctrl-C abort workaround + explicit "known, deferred" note); and the existing-user transition — symptom "I want to switch from my existing `~/.speakloop/qa.yaml` to the new in-repo `content/questions.yaml`", cause "the home-dir file takes precedence (override) over the in-repo default per the resolution order", fix "delete or rename `~/.speakloop/qa.yaml` and the in-repo default takes effect" (surfaces the transition path the new resolution model creates; extends beyond the FR-023 minimum set). Every entry ends in a local fix or an explicit known-v1-limitation statement (FR-022, FR-023, FR-024; research.md R7) (depends on T013)

**Checkpoint**: Every spec-named failure mode has a scannable, honest entry.

---

## Phase 5: User Story 3 - Portable on any machine, enforced automatically (Priority: P2)

**Goal**: An automated audit fails on any machine-specific absolute path across all
tracked content, so the portability guarantee holds over time.

**Independent Test**: Run the audit on the current tree → zero leaks; inject a fake
concrete `/Users/<concrete>/` leak → audit fails; remove it → passes. (Independent of
the question-relocation work; needs only the repo.)

- [X] T015 [P] [US3] Implement the path-portability audit in `tests/integration/test_path_portability_audit.py`: a `find_leaks(repo_root) -> list["path:line"]` helper that enumerates tracked files via `git ls-files -z`, scans decodable text for the leak patterns `(/Users/|/home/)[A-Za-z0-9._-]+/` and `[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\`, excludes portable `~/…` and angle-bracket placeholders and its own module file, returns sorted results; stdlib + git only — **also satisfies FR-028 (no new dependency) by construction** (FR-007, FR-008, FR-009, FR-028; contracts/path-audit.md)
- [X] T016 [US3] In the same test module, add assertions: `find_leaks(repo_root) == []` on the current tree (FR-010, SC-B); a positive self-test that a synthetic concrete-login path (a `/Users/` prefix plus a real-looking name) is detected; negative self-tests that `"~/.speakloop/qa.yaml"` and `"/Users/<name>/x"` are NOT detected (FR-009); and a wall-clock assertion that `find_leaks(repo_root)` completes in under 2 s (FR-011, SC-G) (depends on T015)
- [X] T017 [US3] Run the audit; remove any machine-specific absolute-path leak it reports so it passes on the current tree (research.md R6 expects zero; this task confirms or remediates) (depends on T015)

**Checkpoint**: `uv run pytest tests/integration/test_path_portability_audit.py` passes deterministically in < 2 s and fails on injected leaks.

---

## Phase 6: User Story 4 - Bring your own question set (Priority: P3)

**Goal**: A returning user points the tool at a personal question file outside the repo
and it is used in preference to the in-repo default, without modifying tracked files.

**Independent Test**: With a personal file at `~/.speakloop/qa.yaml`, run a session and
confirm the personal questions load; remove it and confirm fallback to the in-repo default.

- [X] T018 [US4] Document the override in `README.md`: state the `~/.speakloop/qa.yaml` location, the `--qa-file PATH` flag, and the precedence (override wins over the in-repo default) (FR-003 documentation; acceptance scenario 3) (depends on T010)
- [X] T019 [P] [US4] Add an integration test in `tests/integration/test_qa_override_precedence.py`: when `~/.speakloop/qa.yaml` exists it is loaded over `content/questions.yaml`; when absent, resolution falls back to `content/questions.yaml` (acceptance scenarios 1–2; edge case "both exist → override wins")

**Checkpoint**: Override precedence verified in both directions; existing users preserved.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all stories.

- [X] T020 Run the full suite `uv run pytest` and confirm it is green, including the migrated question-loader tests; this is also the verification gate for FR-027 (preserve governing principles: offline-first, English-only, `schema_version` unchanged, modular boundaries, swappable engines) (FR-005, FR-027)
- [X] T021 Walk through `specs/004-public-release-readiness/quickstart.md` / README end-to-end and confirm a developer can answer all SC-C questions from the README alone (~5-min read, FR-020)
- [X] T022 [P] Run `uv run ruff check` and `uv run ruff format --check` on changed files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup (T001). Blocks US1 and US4.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on US1 T008 (shares `README.md`).
- **US3 (Phase 5)**: independent — needs only the repo; may start right after Setup.
- **US4 (Phase 6)**: depends on Foundational (resolution) and US1 T010 (README anchor).
- **Polish (Phase 7)**: after all desired stories.

### User Story Dependencies

- **US1 (P1)**: Foundational only. MVP.
- **US2 (P2)**: README content appended after US1's README skeleton (same file → sequential, not parallel, with US1).
- **US3 (P2)**: fully independent (new test file only).
- **US4 (P3)**: Foundational + US1's "where things live" README anchor.

### Within Stories

- README tasks editing `README.md` (T008→T009/T010, T013→T014, T018) are sequential — same file.
- Audit impl (T015) before its assertions (T016) and remediation (T017).

### Parallel Opportunities

- Setup: T001 and T002 in parallel.
- US3 (T015→T016→T017) can run in parallel with all README work — different files.
- T011 (CLAUDE.md docs) parallel with README tasks — different files.
- T019 (override test) parallel with T018 (README) — different files.

---

## Parallel Example

```bash
# After Setup, US3 (audit) can run concurrently with the US1/US2 README work:
Task: "Implement path-portability audit in tests/integration/test_path_portability_audit.py"   # T015
Task: "Rewrite README.md opening (pitch/platforms/install/quickstart)"                          # T008
Task: "Update content/, config/, top-level CLAUDE.md for new default location"                  # T011
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE**:
   clone → README → finished report on a fresh machine. This alone is a coherent
   public release (questions in-repo + README + license).

### Incremental Delivery

1. Setup + Foundational → resolution backbone ready, suite green.
2. US1 → discoverable questions + README + first report (MVP, demo).
3. US2 → self-service troubleshooting + honest limitations.
4. US3 → portability gate enforced in CI (independent; can land any time after Setup).
5. US4 → personal override documented + tested.
6. Polish → full suite green, quickstart validated, lint clean.

---

## Notes

- No new third-party dependency (FR-028); audit is stdlib + `git`.
- Report `schema_version` stays 1 — no frontmatter change in this feature.
- `loader.load(path)` signature unchanged (FR-005); only test fixture reads migrate.
- Commit after each task or logical group (Conventional Commits).
