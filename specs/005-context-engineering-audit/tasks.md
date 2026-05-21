---
description: "Task list for Context Engineering Audit & Rewrite of the CLAUDE.md Layer"
---

# Tasks: Context Engineering Audit & Rewrite of the CLAUDE.md Layer

**Input**: Design documents from `/specs/005-context-engineering-audit/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/anatomy-contract.md, contracts/audit-pass-fail-contract.md, quickstart.md

**Tests**: No new tests are in scope (FR-053). The only "test" work is (a) running the
existing `pytest` suite green throughout (SC-H) and (b) verifying documented commands by
actually running them (SC-I). The `tests/integration/test_path_portability_audit.py` gate
is run, not authored.

**Organization**: Tasks are grouped by user story. US1 (top-level `CLAUDE.md`) is the MVP
and is independently shippable. US2 (13 module files) and US3 (scoped rules + research doc
+ footprint) layer on top and never break US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)
- Every task names an exact file path.

## Path Conventions

- Deliverable docs: `CLAUDE.md` (root), `src/speakloop/<module>/CLAUDE.md` (×13),
  `doc/research_context_engineering.md`, optional `.claude/rules/*.md`.
- Audit evidence persists under `specs/005-context-engineering-audit/audit/`.
- Read-only ground truth (NEVER modified): `src/speakloop/**/*.py`, `tests/**`,
  `pyproject.toml`, `.specify/memory/constitution.md`, `specs/001`–`specs/004`, `README.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Capture the pre-edit baseline so "no code changes" and "suite stays green" are
provable, and create the place audit evidence will live.

- [x] T001 Capture the pre-edit baseline: run `uv run pytest` and save the summary to `specs/005-context-engineering-audit/audit/baseline-pytest.txt`; run `git rev-parse HEAD` and `git status --porcelain` and record both at the top of that file as the "before" reference (SC-H, G8).
- [x] T002 [P] Create the audit evidence directory `specs/005-context-engineering-audit/audit/` and add `specs/005-context-engineering-audit/audit/README.md` listing the audit deliverable files to be produced in Phase 2 / US1: `divergence-inventory.md`, `module-read-list.md`, `command-matrix.md`, `trap-evidence.md`, `cross-reference-check.md`, `engine-import-scan.md`, `claude-md-inventory.md`, `test-coupling.md`, `footprint.md`, `adversarial-review-verdict.md` (plus `toolchain.txt` and `baseline-pytest.txt` from Setup).
- [x] T003 [P] Verify the toolchain the audit depends on is present and record versions in `specs/005-context-engineering-audit/audit/toolchain.txt`: `uv --version`, `python3 --version` (expect 3.12), `ruff --version`, `rg --version` (audit tooling = stdlib + git + ripgrep).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish ground truth from the code BEFORE any `CLAUDE.md` is rewritten. No
file is rewritten until its claims have a ground-truth row (FR-001–FR-007). These eight
deliverables block all of US1/US2/US3.

**⚠️ CRITICAL**: No rewrite (US1/US2/US3) may begin until this phase is complete.

- [x] T004 [P] Produce the engine-import owner map (FR-006, SC-L): run `rg -n "^\s*(import|from)\s+(mlx_whisper|silero_vad|onnxruntime|parakeet_mlx|mlx_lm|kokoro)" src/speakloop/`, confirm each directly-imported engine package resolves to exactly one wrapper file, and record the table (engine → owning file → import lines) plus the `onnxruntime`-transitive finding (D-1) in `specs/005-context-engineering-audit/audit/engine-import-scan.md`.
- [x] T005 [P] Produce the CLAUDE.md inventory (SC-A baseline): run `find . -name CLAUDE.md -not -path '*/node_modules/*' | xargs wc -l` and record current line counts vs ceilings (root < 200, module < 100) for all 14 files in `specs/005-context-engineering-audit/audit/claude-md-inventory.md`.
- [x] T006 Produce the module-read list AND the inter-module dependency graph (FR-002, FR-007, FR-034): read each of the 13 modules' `__init__.py` and primary public entry points under `src/speakloop/{asr,audio,cli,config,content,debrief,feedback,installer,llm,metrics,sessions,trends,tts}/`, and record one verified-summary line per module (public interface, internal deps, consumers, engine boundary if any) in `specs/005-context-engineering-audit/audit/module-read-list.md`. Derive the module dependency graph from an actual cross-module import scan (`rg -n "^\s*(from|import)\s+speakloop\." src/speakloop/`, not from prose) and record the edge list — this graph is what T016 consumes for the top-level `layout` section (FR-007). No module file may be rewritten in US2 unless it appears here.
- [x] T007 [P] Produce the command matrix (FR-003, FR-012, SC-I): for every command claimed in any `CLAUDE.md` plus the candidate build/test/lint set, actually run it — `speakloop --help`, `speakloop doctor`, `uv run pytest`, `uv run pytest -m live_asr` (note if hardware-gated), `ruff check` — and record each as verified/failed/missing with the exact invocation string in `specs/005-context-engineering-audit/audit/command-matrix.md`. Resolve `speakloop doctor` by running it (record exit code).
- [x] T008 [P] Produce the trap-evidence list (FR-004, FR-011, SC-D): trace each candidate trap to a commit hash, session-report path, or `specs/` reference via `git log` and the seed list in research §F; retain only evidence-backed entries (≥ 5 must survive) and record them in `specs/005-context-engineering-audit/audit/trap-evidence.md`.
- [x] T009 [P] Produce the cross-reference link check (FR-005, SC-J): resolve every `[text](path)` and bare `path/` pointer in all 14 `CLAUDE.md` files against the filesystem and record each as resolves/broken in `specs/005-context-engineering-audit/audit/cross-reference-check.md`; list any broken link as a to-fix item for US1/US2.
- [x] T010 [P] Produce the test-coupling finding (FR-054, SC-H): run `rg -ln "CLAUDE\.md" tests/` and classify each hit as content-assertion vs comment; record the finding (expected: only `test_help_without_models.py` docstring comment, no content assertion) in `specs/005-context-engineering-audit/audit/test-coupling.md`.
- [x] T011 Initialize the divergence inventory (FR-001): create `specs/005-context-engineering-audit/audit/divergence-inventory.md` with the columns `id | claim (doc file:line) | ground truth (code file:line) | severity | action`, seeded with D-1…D-5 from research §D, to be appended during US1/US2 as new divergences surface.
- [x] T012 [P] Measure and record the launch-footprint baseline (FR-043, SC-K): run the tiktoken command from research §A (`uv run --with tiktoken …`) with the stdlib `chars/4` fallback against the current `CLAUDE.md`, and record the baseline token count vs the ≤ 6000 ceiling in `specs/005-context-engineering-audit/audit/footprint.md`.

**Checkpoint**: Ground truth is captured for every claim. Rewrites may now begin.

---

## Phase 3: User Story 1 - Trustworthy launch-time map for any AI agent (Priority: P1) 🎯 MVP

**Goal**: Rewrite the top-level `CLAUDE.md` to the canonical 9-section anatomy with a
maintenance section, every fact code-true, every command verified, ≥ 5 evidence-cited
traps — and pass a fresh adversarial-review sub-agent with 0 CRITICAL / 0 MAJOR.

**Independent Test**: Rewrite only the top-level `CLAUDE.md` and run the adversarial review
against the code (research §I) — the file delivers a complete, trustworthy onboarding map
on its own, regardless of whether US2/US3 ship.

### Implementation for User Story 1

- [x] T013 [US1] Update the SPECKIT-managed block at the top of `CLAUDE.md` so 005 is the active feature and prior features are terse (divergence D-5); preserve the `<!-- SPECKIT START -->`…`<!-- SPECKIT END -->` markers intact and machine-updatable (FR-015, anatomy-contract root rule).
- [x] T014 [US1] Rewrite the human-authored region of `CLAUDE.md` to the fixed 9-section anatomy in order — `overview → tech-stack → layout → commands → conventions → maintenance → traps → never-do → pointers` (FR-010, data-model top-level anatomy, anatomy-contract). All nine sections present and non-empty.
- [x] T015 [US1] Author the `tech-stack` section of `CLAUDE.md` from `pyproject.toml`, confirmed against actual imports: Python 3.12, `uv`, `mlx-whisper`, `mlx-lm`, `kokoro-mlx`, `silero-vad`, `onnxruntime` (transitive via silero), `parakeet-mlx`, the `torchaudio<2.9` cap, plus `typer`/`rich`/`pyyaml`/`sounddevice`/`huggingface_hub`/`numpy` — no aspirational deps; use `kokoro_mlx` naming (divergence D-2).
- [x] T016 [US1] Author the `layout` section of `CLAUDE.md` (module map + dependency rules) directly from the engine-import scan and module-read list (`audit/engine-import-scan.md`, `audit/module-read-list.md`), not from prior prose (FR-007); keep the 13-module table with working pointers to each module's `CLAUDE.md`.
- [x] T017 [US1] Author the `commands` section of `CLAUDE.md` from `audit/command-matrix.md`, including ONLY commands with `status = verified`; remove any failing/missing command and add any verified-but-undocumented one (FR-012, anatomy-contract: commands MUST be verified).
- [x] T018 [US1] Author the `conventions` section of `CLAUDE.md`, each convention cross-verified against code and the constitution (e.g., function-local engine imports per Principle VIII, English-only per Principle I, additive `schema_version`); no convention may contradict a constitution principle.
- [x] T019 [US1] Author the `maintenance` ("how to maintain this context layer") section of `CLAUDE.md` verbatim from the 7-item checklist in research §J: feature-driven cadence (every new `specs/NNN-*` triggers a review + per-PR convention-change coupling, no calendar interval), correct-twice-then-record, PR-coupling, split-on-overflow; concrete rules only, applicable in < 2 minutes (FR-020, SC-E, G5).
- [x] T020 [US1] Author the `traps` section of `CLAUDE.md` with ≥ 5 entries, each citing a commit hash / session-report path / `specs/` reference drawn from `audit/trap-evidence.md` (FR-011, SC-D, G4).
- [x] T021 [US1] Author the `never-do` section of `CLAUDE.md`, citing a code pattern where one applies (e.g., no module-level engine import; no `/Users/...` personal path in any committed file; never raise `schema_version`).
- [x] T022 [US1] Author the `pointers` section of `CLAUDE.md` to per-module `CLAUDE.md` files, `specs/`, `doc/research_*.md`, and the constitution; prefer pointers over `@`-imports, import depth ≤ 5 (FR-055); put any human-only "why" notes in HTML comments (zero context cost).
- [x] T023 [US1] Fix every broken cross-reference originating in `CLAUDE.md` per `audit/cross-reference-check.md` (FR-005, SC-J); append any newly found divergence to `audit/divergence-inventory.md`.
- [x] T024 [US1] Verify `CLAUDE.md` is < 200 lines and entirely English (`wc -l CLAUDE.md`); split detail into module files if over (FR-013, SC-A, G1).
- [x] T025 [US1] Re-run the documented commands from the rewritten `commands` section to confirm each still passes as written, and update `audit/command-matrix.md` (SC-I, G9).
- [x] T026 [US1] Run the fresh adversarial-review sub-agent on `CLAUDE.md` using the exact prompt and scope in research §I (reads only `CLAUDE.md` + `src/speakloop/**` + `tests/**` + `pyproject.toml` + constitution); save its severity-classified divergence table and one-line VERDICT to `specs/005-context-engineering-audit/audit/adversarial-review-verdict.md` (FR-014, SC-C, G3).
- [x] T027 [US1] If the verdict is FAIL, fix every named CRITICAL/MAJOR claim in `CLAUDE.md`, append the corrections to `audit/divergence-inventory.md`, and re-run T026 until VERDICT = PASS (0 CRITICAL, 0 MAJOR); record the final PASS (G3 gate).

**Checkpoint**: The top-level `CLAUDE.md` is a complete, code-true, review-passing launch
map. US1 is independently shippable as the MVP.

---

## Phase 4: User Story 2 - On-demand module guidance that loads only when needed (Priority: P2)

**Goal**: Rewrite all 13 module `CLAUDE.md` files to the shared module anatomy (Principle IV
six fields, module-adapted order), each verified against its module's code, each engine
boundary named — without adding launch tokens (modules load just-in-time).

**Independent Test**: Rewrite the 13 module files to the shared anatomy and verify each
engine import lives in exactly one wrapper — testable module-by-module against the code
without touching the top-level file.

### Implementation for User Story 2

> Each module rewrite uses the module anatomy in data-model.md (`purpose →
> public-interface → dependencies → consumers → file-map → modification-patterns →
> [traps] → [never-do] → [pointers]`), keeps the six mandatory fields, omits inapplicable
> optional sections (no "N/A" padding), stays < 100 lines and English, and draws facts
> from `audit/module-read-list.md` (FR-030–FR-034, anatomy-contract module rules). The
> three engine-owning modules MUST name their boundary in `dependencies` (FR-032).

- [x] T028 [P] [US2] Rewrite `src/speakloop/asr/CLAUDE.md` to the module anatomy; name the engine boundary in `dependencies` — `mlx_whisper` (whisper_mlx_engine.py), `silero_vad` (vad.py), `parakeet_mlx` (parakeet_engine.py) — and document `onnxruntime` as transitive-via-silero, not an owned import (corrects divergence D-1).
- [x] T029 [P] [US2] Rewrite `src/speakloop/llm/CLAUDE.md` to the module anatomy; name the engine boundary `mlx_lm` (qwen_engine.py) in `dependencies` (FR-032); expand from current thin state to cover all six Principle IV fields.
- [x] T030 [P] [US2] Rewrite `src/speakloop/tts/CLAUDE.md` to the module anatomy; name the engine boundary `kokoro_mlx` (kokoro_engine.py) in `dependencies` (FR-032, divergence D-2 naming); expand to cover all six fields.
- [x] T031 [P] [US2] Rewrite `src/speakloop/audio/CLAUDE.md` (thinnest today, 9 lines) to the module anatomy covering all six Principle IV fields, < 100 lines.
- [x] T032 [P] [US2] Rewrite `src/speakloop/sessions/CLAUDE.md` (thinnest today, 9 lines) to the module anatomy covering all six fields.
- [x] T033 [P] [US2] Rewrite `src/speakloop/metrics/CLAUDE.md` (thin, 11 lines) to the module anatomy covering all six fields.
- [x] T034 [P] [US2] Rewrite `src/speakloop/trends/CLAUDE.md` (thin, 11 lines) to the module anatomy covering all six fields.
- [x] T035 [P] [US2] Rewrite `src/speakloop/cli/CLAUDE.md` to the module anatomy; reflect the verified `practice`/`doctor`/`trends` commands from `audit/command-matrix.md`.
- [x] T036 [P] [US2] Rewrite `src/speakloop/config/CLAUDE.md` to the module anatomy; document the Q&A file precedence (`--qa-file → ~/.speakloop/qa.yaml → repo default`) as a `traps` entry, citing `config/paths.py:resolve_qa_file` and `specs/004-public-release-readiness/` (matches trap-evidence #5 from `audit/trap-evidence.md`).
- [x] T037 [P] [US2] Rewrite `src/speakloop/content/CLAUDE.md` to the module anatomy (default questions at repo-root `content/questions.yaml`; home override opt-in).
- [x] T038 [P] [US2] Rewrite `src/speakloop/installer/CLAUDE.md` to the module anatomy; reflect the manifest/consent/resumable-download/validation responsibilities and the Qwen3-8B-vs-research deviation rationale.
- [x] T039 [P] [US2] Rewrite `src/speakloop/feedback/CLAUDE.md` to the module anatomy (frontmatter, atomic writer, report builder, grammar analyzer).
- [x] T040 [P] [US2] Rewrite `src/speakloop/debrief/CLAUDE.md` to the module anatomy (render + audio + menu).
- [x] T041 [US2] Verify all 13 module files: each < 100 lines and English (`find src/speakloop -name CLAUDE.md | xargs wc -l`), same spine slots in the same relative order (SC-B), every cross-reference resolves (SC-J); append any divergence found to `audit/divergence-inventory.md` and update `audit/claude-md-inventory.md` (G1, G2, G10).

**Checkpoint**: All 14 `CLAUDE.md` files conform to the shared anatomy and are code-true.
US1 still passes its review unchanged.

---

## Phase 5: User Story 3 - Scoped rules and the research reference, within a bounded launch footprint (Priority: P3)

**Goal**: Decide (and only-if-justified add) `.claude/rules/*.md`; sanitize and commit
`doc/research_context_engineering.md`; confirm the path-portability audit stays green and
the launch footprint stays ≤ 6000 tokens with module files contributing zero.

**Independent Test**: Record the scoped-rules decision, commit the sanitized research doc,
and confirm both the path-portability audit passes and the footprint is within budget.

### Implementation for User Story 3

- [x] T042 [US3] Investigate real session friction and decide whether any `.claude/rules/*.md` earns its place (default expectation: zero — research §K). If none is justified, record that decision and rationale in `specs/005-context-engineering-audit/audit/scoped-rules-decision.md`. If one is justified, create `.claude/rules/<name>.md` with `paths` frontmatter scope + an HTML-comment justification (why module-scope rule vs. living in the relevant `CLAUDE.md` vs. skipped) (FR-040, SC-G, G7).
- [x] T043 [US3] Sanitize `doc/research_context_engineering.md`: remove the line-3 maintainer personal path (`/Users/ehsankolivans/...`) and confirm all content is English; do NOT rewrite its Android/Gradle illustrative examples (FR-041, SC-F).
- [x] T044 [US3] Run `uv run pytest tests/integration/test_path_portability_audit.py` and confirm it is green with the sanitized research doc and all `.md` changes staged; record the result in `audit/command-matrix.md` (FR-042, SC-F, G6).
- [x] T045 [US3] Re-measure the final launch footprint with the research §A command (`CLAUDE.md` + any unscoped `.claude/rules/*.md`) and confirm ≤ 6000 tokens; confirm module `CLAUDE.md` files and any `paths`-scoped rules contribute zero launch tokens; update `specs/005-context-engineering-audit/audit/footprint.md` (FR-043, SC-K, G11). If over budget, push detail from `CLAUDE.md` into a module file or scoped rule and re-measure.

**Checkpoint**: Scoped-rules decision recorded, research doc sanitized and audit-green,
footprint within budget. All three stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns (final gate)

**Purpose**: Verify the full pass/fail contract (G1–G16) and the non-regression guardrails
across all stories.

- [x] T046 Run the full suite `uv run pytest` and confirm all pass with no test broken by `CLAUDE.md` changes; compare against `audit/baseline-pytest.txt` (SC-H, FR-053, G8).
- [x] T047 [P] Confirm no code changed: `git diff --name-only` shows only `*.md` and `.claude/rules/` files touched — no `src/**/*.py`, `tests/**`, or `pyproject.toml` (FR-053, G13).
- [x] T048 [P] Confirm read-only inputs are unchanged: `git diff` shows `.specify/memory/constitution.md` and `specs/001`–`specs/004` untouched (FR-051, FR-052, G14).
- [x] T049 [P] Confirm FR-055 compliance: `rg "^@|]\(@" CLAUDE.md src/speakloop/*/CLAUDE.md` finds no `@`-import exceeding 5 hops, pointers are used in preference to `@`-imports, and human-only "why" notes / rule justifications live in HTML comments (G16).
- [x] T050 [P] Confirm claim-ledger traceability: every non-obvious decision in the rewritten layer traces to a numbered claim in `doc/research_context_engineering.md` §17; record the mapping in `specs/005-context-engineering-audit/audit/claim-ledger-trace.md` (FR-056, G15).
- [x] T051 Finalize `audit/divergence-inventory.md` (all rows resolved or marked `flag-and-defer`) and walk the full Gate table in `contracts/audit-pass-fail-contract.md` (G1–G16), recording PASS for each in `specs/005-context-engineering-audit/audit/gate-checklist.md`.
- [x] T052 Run the quickstart validation (`specs/005-context-engineering-audit/quickstart.md`) end to end to confirm the audit + sub-agent review reproduce, and note the result in `audit/gate-checklist.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all of US1/US2/US3** — no file is
  rewritten until its claims have a ground-truth row (FR-001–FR-007).
- **US1 (Phase 3)**: Depends on Foundational. The MVP; independently shippable.
- **US2 (Phase 4)**: Depends on Foundational; begins only after US1 is a coherent slice
  (Principle XII). Does not modify `CLAUDE.md`, so it cannot break US1's review.
- **US3 (Phase 5)**: Depends on Foundational; deliberately last and optional. Its footprint
  check (T045) reads the US1/US2 outputs.
- **Polish (Phase 6)**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: Independent — delivers value alone (trustworthy top-level map).
- **US2 (P2)**: Independent of US1's content; touches only the 13 module files.
- **US3 (P3)**: Independent; reads US1/US2 outputs for the footprint measurement but does
  not alter them.

### Within Each User Story

- US1: T013 (SPECKIT block) and T014 (anatomy skeleton) precede the section-authoring tasks
  T015–T022; T023–T025 verify; T026–T027 are the review gate and run last.
- US2: T028–T040 are all parallel (different files); T041 verifies after them.
- US3: T042 / T043 are independent; T044 follows T043; T045 follows US1 + US2 + T042/T043.

### Parallel Opportunities

- Setup: T002, T003 in parallel (T001 captures the baseline first).
- Foundational: T004, T005, T007, T008, T009, T010, T012 are all parallel (distinct audit
  files); T006 (module-read) and T011 (inventory init) can run alongside them.
- US2: all 13 module rewrites (T028–T040) run in parallel — different files, no shared deps.
- Polish: T047, T048, T049, T050 run in parallel.

---

## Parallel Example: User Story 2

```text
# Launch all 13 module-file rewrites together (different files, no shared deps):
Task: "Rewrite src/speakloop/asr/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/llm/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/tts/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/audio/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/sessions/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/metrics/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/trends/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/cli/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/config/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/content/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/installer/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/feedback/CLAUDE.md to the module anatomy"
Task: "Rewrite src/speakloop/debrief/CLAUDE.md to the module anatomy"
# Then T041 verifies all 13 (line counts, anatomy order, cross-refs).
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (baseline + audit dir).
2. Complete Phase 2: Foundational (8 audit deliverables — CRITICAL, blocks all stories).
3. Complete Phase 3: US1 — rewrite the top-level `CLAUDE.md`, verify commands, pass the
   adversarial review (0 CRITICAL / 0 MAJOR).
4. **STOP and VALIDATE**: the top-level map is trustworthy and review-passing on its own.
5. Ship the MVP.

### Incremental Delivery

1. Setup + Foundational → ground truth captured.
2. US1 → adversarial-review PASS → ship (MVP: trustworthy launch map).
3. US2 → all 13 module files conform → ship (just-in-time module guidance).
4. US3 → scoped-rules decision + sanitized research doc + footprint ≤ 6000 → ship.
5. Polish → walk the full G1–G16 gate table → done.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete work.
- Code is the source of truth; the constitution is the sole read-only authority and wins on
  any documentation conflict (FR-051).
- Any finding that would require editing `src/`, `tests/`, or `pyproject.toml` gets a
  divergence row with `action = flag-and-defer` — the doc is written to match current code,
  never the other way around (FR-053, research §G).
- No new tests; "tests" means running the existing suite green (SC-H) and verifying
  documented commands by running them (SC-I).
- Commit after each task or logical group; keep the SPECKIT-managed block terse to protect
  the 6000-token budget.
