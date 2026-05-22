---
description: "Task list for 006-feedback-quality-reliability"
---

# Tasks: Reliable, Higher-Quality Session Feedback

**Input**: Design documents from `specs/006-feedback-quality-reliability/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md, contracts/ (all present)

**Tests**: REQUIRED for this feature. The contracts pin explicit obligations (grammar-output-schema
T-G1..T-G5, eval-set-format T-E1..T-E3, report-invariance V-R1..V-R5); they are tasks below, not
optional. Model-free tests run in CI; live-model measurement is `live_llm`-marked and manual.

**Organization**: By user story, in the priority/sequencing order fixed by `plan.md`
§"Phase sequencing": Foundational (A-EvalSet → A-Baseline) → US1 (P1) → US2 (P2) → US3 (P3) → Polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)
- **[live_llm]**: requires the already-downloaded local model; manual / `live_llm`-marked, excluded
  from default `pytest` (Constitution Dev Guidelines). All other tests are model-free / CI-safe.

## Path Conventions

Single project. Package code under `src/speakloop/`, tests under `tests/`, and the **validation
harness under `eval/` at the repo root — outside the package**, never imported by the CLI or shipped
(`[tool.hatch.build.targets.wheel] packages = ["src/speakloop"]`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The two cross-cutting infra changes every later phase relies on.

- [X] T001 Add `json-repair` to `[project].dependencies` in `pyproject.toml` (the one new dep — offline, pure-Python, zero required runtime deps; the `[schema]` extra is NOT taken). Run `uv sync`. (research Decision 3; grammar-output-schema §C)
- [X] T002 Register a `live_llm` pytest marker in `pyproject.toml` `[tool.pytest.ini_options].markers`, mirroring the existing `live_asr` entry (`pyproject.toml:77`) verbatim in style; live measuring tests are gated by `@pytest.mark.live_llm` + `importorskip` and excluded from default `pytest`, exactly like `tests/integration/test_vad_live_smoke.py`. (plan Testing; the `live_asr` precedent is confirmed to exist)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the measurement instrument and capture the baseline on **current** code.

**⚠️ CRITICAL — golden rule of ordering (quickstart §0)**: the pre-change baseline (T010) and the
pre-registered threshold (T011) MUST be captured BEFORE any analyzer/wrapper change in US1. Once the
code changes, "today's level" is gone.

- [X] T003 Create the `eval/grammar/` skeleton outside the package — `cases/`, `failure_batch/`, `baselines/` directories — plus `eval/grammar/PROTOCOL.md` (labeling rubric + taxonomy + adjudication) and `eval/grammar/README.md` (provenance, de-identification, how-to-run). (plan Structure Decision; eval-set-format; data-model §4)
- [X] T004 [P] Author 20–30 labeled cases in `eval/grammar/cases/case-NNN.yaml` (synthetic / de-identified Persian-L1; verbatim gold quotes; catalog-or-open-bucket labels; INCLUDE some empty-`gold_issues` "correct answer" cases that measure false alarms). (eval-set-format §1 E1–E4; data-model §4)
- [X] T005 [P] Author the ≥100-session **unlabeled failure batch** in `eval/grammar/failure_batch/*.yaml` (synthetic/replayed transcripts drawn from **normal operating conditions** per spec Assumptions — model present, ≥1 non-silent intelligible attempt; same shape as a case file minus `gold_issues`; no human labels). This is the SC-001 instrument; the labeled set can't resolve ~1%. (eval-set-format §3a; data-model §6; SC-001)
- [X] T006 [P] Implement `eval/grammar/run_eval.py`: `--validate-only` (E1–E4 self-check, model-free), `--phase {pre,post}`, `--runs K` (default 3, per-unit median), `--out`; scores agreement (precision/recall/F0.5) on the labeled cases and `failure_rate` on the failure batch in one pass; **offline** (uses only the already-downloaded model; on absence prints "model unavailable — skipped" and exits non-zero with no network fetch). (eval-set-format §3,§3a,§4; data-model §6; FR-020)
- [X] T007 [P] [TEST] T-E1: `eval/grammar/run_eval.py --validate-only` enforces E1–E4 and FAILS on a planted bad case (bad quote / unknown label / planted personal-path leak); model-free, CI-safe — in `tests/unit/eval/test_run_eval_validate.py`. (eval-set-format Test obligations)
- [X] T008 [P] [TEST] T-E2: scorer unit test — a hand-checked prediction↔gold example computes precision/recall/F0.5 and the overlap/label-compat match rule correctly (pure function, no model) — in `tests/unit/eval/test_scorer.py`. (eval-set-format §3; data-model §6)
- [X] T009 [P] [TEST] T-E3: `eval/` contributes ZERO runtime imports to the shipped package (import-graph / wheel-content check) — in `tests/integration/test_eval_not_shipped.py`. (eval-set-format Test obligations; plan Structure Decision)
- [ ] T010 [live_llm] Capture the pre-change baseline on **current, unmodified** code: `uv run python eval/grammar/run_eval.py --phase pre --runs 3 --out eval/grammar/baselines/baseline-pre.yaml` → records `failure_rate` (failure batch), `grammar.{precision,recall,f05}` (labeled set), `failure_batch_size`, `n_labeled_cases`, `runs_per_case`. **Must precede US1.** (quickstart §0,§2; research A-Baseline; FR-020) ← DEFERRED (live_llm, manual per tasks.md Notes): ~435 model generations (~2h) exceeds the autonomous foreground budget. Mitigation: the Foundational-phase git commit preserves the unmodified pre-US1 analyzer/wrapper, so a true `--phase pre` baseline is recoverable from that commit (README §"golden rule of ordering"). Harness is built & validated; only the on-device run is pending.
- [X] T011 Pre-register the deferred **SC-002 F0.5 improvement threshold** at baseline-capture time so it is versioned/auditable, not tribal knowledge: write it into a `thresholds:` block in `eval/grammar/baselines/baseline-pre.yaml` (or a sibling `eval/grammar/baselines/thresholds.yaml`). (spec SC-002; quickstart §2)

**Checkpoint**: harness validated (T007–T009 green), baseline + threshold locked. Analyzer changes may begin.

---

## Phase 3: User Story 1 - Every finished session yields complete, usable analysis (Priority: P1) 🎯 MVP

**Goal**: Under normal conditions the report reliably arrives complete and well-formed — grammar
feedback present (not the fluency-only fallback), nothing raw/garbled/truncated/looping/duplicated;
malformed model output is recovered or degrades gracefully; structure identical to today.

**Independent Test**: Replay the failure batch (varied lengths, messy L2) — `failure_rate ≤ 0.01`
and below baseline, zero garbled/looping/duplicate output, report structure byte-for-structure identical.

### Tests for User Story 1 (write FIRST; most must FAIL before implementation) ⚠️

- [ ] T012 [P] [US1] Extract the FULL catalog of bad-JSON cases the current logic handles — read the regexes in `feedback/grammar_analyzer.py:89-150` (`_strip_code_fences`, `_TRAILING_COMMA_RE`, `_JUNK_TOKEN_BEFORE_KEY_RE`, `_SINGLE_QUOTED_KEY_RE`, `_BARE_KEY_RE`, `_SINGLE_QUOTED_VALUE_RE`, `_loads_lenient`/`json5`) plus any existing fixtures and any `SPEAKLOOP_DEBUG_LLM` raw dumps — and convert EACH into a fixture under `tests/unit/feedback/fixtures/bad_json/` (single-quoted keys, bare/unquoted keys, single-quoted values, trailing comma, ```json fence, stray ``` lines, junk-token-before-key, truncated/cut-off object, prose-before-and-after). This corpus DEFINES T-G2 (prevents silent regression on edge cases the regex caught). (user-flagged item 1)
- [ ] T013 [P] [US1] [TEST] T-G2: each fixture from T012 recovers via `json-repair` to the SAME verified patterns as a clean parse (cached fixtures + monkeypatched `mlx_lm`, no live model) — in `tests/unit/feedback/test_grammar_repair.py`. (grammar-output-schema T-G2; depends on T012)
- [ ] T014 [P] [US1] [TEST] T-G1: a golden well-formed flat-schema response parses with ZERO repair to the expected verified patterns — in `tests/unit/feedback/test_grammar_repair.py`. (grammar-output-schema T-G1)
- [ ] T015 [P] [US1] [TEST] T-G3: a repetition-loop / `finish_reason=="length"` fixture triggers EXACTLY ONE bounded regenerate, then either succeeds or falls back cleanly with no hang — in `tests/unit/feedback/test_grammar_recovery.py`. (grammar-output-schema T-G3; FR-002, FR-003)
- [ ] T016 [P] [US1] [TEST] T-G4: the wrapper passes `temperature=0.7, top_p=0.8, top_k=20, min_p=0, repetition_penalty=1.05, repetition_context_size=40, stop=["<|im_end|>"], enable_thinking=False`, asserted via monkeypatched `mlx_lm` (no live model) — in `tests/unit/llm/test_qwen_generation_config.py`. (grammar-output-schema §B, T-G4)
- [ ] T017 [P] [US1] [TEST] T-G5: the no-model import guard still holds (`mlx_lm` import stays function-local; importing the CLI loads no engine package) — extend `tests/integration/test_help_without_models.py`. (grammar-output-schema T-G5; root CLAUDE.md trap 2)

### Implementation for User Story 1

- [ ] T018 [P] [US1] In `src/speakloop/llm/qwen_engine.py`: construct the non-thinking sampler (`make_sampler` default `temperature=0.7`) + `make_logits_processors(repetition_penalty=1.05, repetition_context_size=40)` + `stop=["<|im_end|>"]`; keep `enable_thinking=False`. All engine specifics stay inside the wrapper (Principle V). (grammar-output-schema §B; research R1,R2,R5)
- [ ] T019 [P] [US1] In `src/speakloop/llm/interface.py`: keep `generate()` signature stable OR add additive optional params with research defaults — no call-site leakage of engine config. (grammar-output-schema §B)
- [ ] T020 [US1] In `src/speakloop/feedback/grammar_analyzer.py`: REMOVE the `temperature=0.2` call-site override in `analyze()` (line 266) so the wrapper owns the research-aligned 0.7. (grammar-output-schema §B "remove the temperature=0.2 override")
- [ ] T021 [US1] In `src/speakloop/feedback/grammar_analyzer.py`: replace the hand-rolled repair (`_repair_json`, `_loads_lenient`, optional `json5`) with `json-repair` in the recovery ladder (`json.loads` → `json_repair.loads` → … → graceful fallback); KEEP `_strip_code_fences`, the `<think>`-leakage guard, and `_extract_json`. Must pass every T012 fixture. (grammar-output-schema §C; data-model §2; depends on T012)
- [ ] T022 [US1] In `src/speakloop/feedback/grammar_analyzer.py`: add the bounded regenerate (≤1) on repetition-loop / length — re-call with `repetition_penalty↑≈1.15, temperature −0.1`; on terminal failure preserve EXACTLY today's graceful path (`phase_c_error` set, Phase-B report rendered, session never crashes). (grammar-output-schema §C; FR-002, FR-003)
- [ ] T023 [US1] In `src/speakloop/feedback/grammar_analyzer.py`: dedupe so no repeated/near-duplicate restatement reaches the report — merge patterns sharing a normalized label (sum `occurrence_count`, union evidence) before ranking. (FR-004; data-model §1)
- [ ] T024 [US1] Confirm V1–V5 still hold after T020–T023 (verbatim substring, coherence filter, no-op-fix drop, open-bucket gate, deterministic `(impact_rank, -occurrence_count, first_attempt_ordinal)` sort) — the recovery/dedupe changes strengthen inputs but MUST NOT weaken any guarantee. (data-model §1; grammar-output-schema post-conditions)
- [ ] T025 [P] [US1] Update `src/speakloop/llm/CLAUDE.md` (rep-penalty/stop/sampler config now owned here) and `src/speakloop/feedback/CLAUDE.md` (json-repair replaces regex repair; bounded regenerate) in the same commit as the code change (root CLAUDE.md PR-coupling rule).

**Checkpoint**: US1 is the MVP — reports reliably arrive clean. Stop and validate against the failure batch before US2.

---

## Phase 4: User Story 2 - Grammar suggestions are accurate and useful (Priority: P2)

**Goal**: Flagged items are real errors anchored to verbatim coherent fragments, corrections are
themselves correct, explanations are plain language; fewer false alarms AND fewer misses; no issue
reported twice.

**Independent Test**: Re-measure agreement on the labeled set (post vs `baseline-pre`): F0.5 clears
the pre-registered threshold AND neither precision nor recall regresses.

### Implementation for User Story 2

- [ ] T026 [US2] Tune the system prompt in `src/speakloop/feedback/grammar_analyzer.py` (`_build_system_prompt`): keep the FLAT schema, add ≤2 few-shot examples, tighten label/evidence/correction/explanation guidance; do NOT introduce nested `oneOf`/optional objects (4-bit drift). (grammar-output-schema §A; research R7)
- [ ] T027 [US2] [live_llm] Re-measure agreement with the tuned prompt: `uv run python eval/grammar/run_eval.py --phase post --runs 3 --out eval/grammar/baselines/post.yaml`; confirm the SC-002 bar — F0.5 clears the pre-registered threshold (T011) AND neither precision nor recall falls below `baseline-pre`. Add a 3rd few-shot only if schema drift appears. The model stays `mlx-community/Qwen3-8B-4bit` (8-bit out of scope — Decision 2). (spec SC-002; quickstart §3,§4)

**Checkpoint**: US1 + US2 both hold independently; grammar content is measurably better.

---

## Phase 5: User Story 3 - Narrative and top-priority are trustworthy (Priority: P3)

**Goal**: The cross-attempt narrative is coherent prose grounded ONLY in the session's transcripts
and metrics (no invented facts); the single "top priority" is the most impactful item by a stable,
reproducible rule. Both stay deterministic (Decision 1) and improve from cleaner US1/US2 inputs.

**Independent Test**: Blind paired review judges post narratives more grounded and top-priority picks
more meaningful; no narrative clause asserts an unsupported fact; report structure is unchanged.

### Implementation for User Story 3

- [ ] T028 [US3] Tighten the DETERMINISTIC narrative in `src/speakloop/feedback/narrative.py`: every clause grounded in the session's transcripts/metrics; drop any ungrounded phrasing; degrade to today's sensible defaults on silent/empty input. Stays deterministic and reproducible (no LLM). (FR-011, FR-013; research Decision 1; report-invariance "what MAY change")
- [ ] T029 [US3] Confirm the deterministic top-priority selection in `src/speakloop/feedback/narrative.py` is reproducible from the report itself and drawn only from the session's own issues/metrics by a stable rule (it inherits cleaner inputs; the rule itself is unchanged). (FR-012; data-model V5; research Decision 1)

### Tests for User Story 3 (report-invariance guardrail) ⚠️

- [ ] T030 [P] [US3] [TEST] V-R1: existing report/format/golden tests pass; if any assert exact narrative wording, update the golden text AND confirm the STRUCTURE is untouched (wording diff allowed, structural diff not) — in `tests/unit/feedback/`. (report-invariance V-R1; SC-005)
- [ ] T031 [P] [US3] [TEST] V-R2: frontmatter `dump → parse → dump` is idempotent and `schema_version` stays `1` (no bump) — in `tests/unit/feedback/test_report_invariance.py`. (report-invariance V-R2; FR-018)
- [ ] T032 [P] [US3] [TEST] V-R3: a pre-feature report vs a post-feature CLEAN report differ only in grammar/narrative CONTENT — empty structural diff (identical key set, section set, ordering); also confirms no new feedback dimension/section (FR-015) — in `tests/unit/feedback/test_report_invariance.py`. (report-invariance V-R3; SC-005, FR-014)
- [ ] T033 [P] [US3] [TEST] V-R4: zero network calls during a full session+analysis (reuse the engine-import offline guard) — in `tests/integration/test_no_network_during_session.py`. (report-invariance V-R4; SC-006, FR-016)
- [ ] T034 [P] [US3] [TEST] V-R5: the model is unchanged — `mlx-community/Qwen3-8B-4bit` (family AND quantization), no swap — in `tests/unit/llm/test_model_family_unchanged.py`. (report-invariance V-R5; FR-017)

**Checkpoint**: all three stories independently functional; report is reliable, accurate, and trustworthy.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T035 [live_llm] Capture the final `post` measurement and read the verdict (quickstart §4): SC-001 `failure_rate ≤ 0.01` over the failure batch and below baseline; SC-002 F0.5 clears threshold + no precision/recall regression; SC-004 zero garbled/looping/malformed/duplicate findings across the run. (quickstart §3,§4; SC-001/002/004)
- [ ] T036 [live_llm] Subjective blind paired review (SC-003, SC-007): sample recent pre-change vs post-change reports; confirm post narrative more accurate/grounded and top-priority more meaningful in a clear majority, and that sampled corrections are grammatically correct with plain-language explanations. (quickstart §5)
- [ ] T037 [P] Principle X: reflect the new sampler/repetition-penalty/stop config and the firm **4-bit-only** decision (8-bit out of scope this sprint) in `doc/research_llm.md`; cross-link `doc/QWEN_IMPROVMENT_RESEARCH.md`. (plan Constitution Check ⚠ Principle X)
- [ ] T038 [P] Root `CLAUDE.md`: update Traps (json-repair replaces regex repair; rep-penalty/stop/temp-0.7 owned in `qwen_engine.py`), run the 7-item feature-driven maintenance checklist, and re-measure the launch footprint (≤ 6000 tokens). (root CLAUDE.md maintenance)
- [ ] T039 Full green gate: `uv run pytest` (existing 306+ pass, plus the new model-free tests), `uv run speakloop --help` loads no engine package, and `uv run pytest tests/integration/test_path_portability_audit.py` passes over `eval/` (no personal paths). (quickstart §6; SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup. **BLOCKS all user stories.** Within it: T003 → (T004, T005, T006 in parallel) → (T007–T009 tests) → T010 baseline → T011 threshold. T010/T011 MUST finish before any US1 implementation task (golden rule of ordering).
- **US1 (Phase 3)**: depends on Foundational. This is the MVP.
- **US2 (Phase 4)**: depends on US1 (accuracy can't be measured until output is reliable; T027 needs the US1 recovery path live).
- **US3 (Phase 5)**: depends on US1 (and benefits from US2) — narrative/top-priority inherit cleaner inputs; invariance tests need the content changes in place.
- **Polish (Phase 6)**: depends on US1–US3. T035 before T036 (review reads post reports); T039 last.

### Key within-story dependencies

- T012 (fixture catalog) → T013 (T-G2 assertion) and → T021 (repair swap).
- T018/T019 (wrapper config) verified by T016 (T-G4).
- T020 → T021 → T022 → T023 → T024 are the SAME file (`grammar_analyzer.py`) — sequential, not parallel.
- T028 → T029 are the SAME file (`narrative.py`) — sequential.
- T026 → T027 (measure tuned prompt).

### Parallel opportunities

- Setup: T001 then T002 (both edit `pyproject.toml` — sequential).
- Foundational: T004, T005, T006 in parallel; then T007, T008, T009 in parallel.
- US1 tests: T012 first, then T013–T017 in parallel; wrapper tasks T018, T019 parallel; doc T025 parallel.
- US3 tests: T030–T034 all parallel (distinct files).
- Polish: T037, T038 parallel.

---

## Parallel Example: Foundational harness tests (after T006)

```bash
Task: "T-E1 --validate-only enforcement in tests/unit/eval/test_run_eval_validate.py"
Task: "T-E2 scorer precision/recall/F0.5 in tests/unit/eval/test_scorer.py"
Task: "T-E3 eval/ adds zero runtime imports in tests/integration/test_eval_not_shipped.py"
```

## Parallel Example: User Story 1 tests (after T012)

```bash
Task: "T-G2 repair-fixture recovery in tests/unit/feedback/test_grammar_repair.py"
Task: "T-G1 golden zero-repair parse in tests/unit/feedback/test_grammar_repair.py"
Task: "T-G3 one bounded regenerate in tests/unit/feedback/test_grammar_recovery.py"
Task: "T-G4 wrapper generation-config in tests/unit/llm/test_qwen_generation_config.py"
Task: "T-G5 no-model import guard in tests/integration/test_help_without_models.py"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL — capture baseline + threshold on current code
FIRST) → 3. Phase 3 US1 → 4. STOP and validate against the failure batch (`failure_rate ≤ 0.01`, zero
garbled/duplicate, structure unchanged). US1 alone is a shippable, demonstrable slice: reports stop
failing and stop showing broken output.

### Incremental delivery

- Foundational ready → US1 (MVP, reliability) → US2 (grammar accuracy) → US3 (narrative + top-priority)
  → Polish (final post measurement, blind review, Principle X + CLAUDE.md).
- Each story adds value without breaking the previous; the report-invariance tests (US3) guard that the
  user-visible format never changes across the whole sprint.

---

## Notes

- **Tests are required here** (contract-pinned): T-G1..T-G5, T-E1..T-E3, V-R1..V-R5 all appear above.
- Model-free tests (everything except `[live_llm]`) run in default `pytest` / CI. The `[live_llm]`
  measurement tasks (T010, T027, T035, T036) are manual on a machine with the model downloaded.
- `[P]` = different files, no incomplete dependency. Same-file task chains (grammar_analyzer.py,
  narrative.py, pyproject.toml) are intentionally sequential.
- Commit after each task or logical group; keep module `CLAUDE.md` updates in the same commit as the
  code they describe (root CLAUDE.md PR-coupling rule).
- The report's persisted `schema_version` stays **1**; no frontmatter key is added this sprint
  (data-model §3 keeps recovery telemetry in-process only).
- This sprint stays on `mlx-community/Qwen3-8B-4bit`; the 8-bit variant is out of scope (Decision 2 —
  Constitution VI/VII bandwidth/RAM).
