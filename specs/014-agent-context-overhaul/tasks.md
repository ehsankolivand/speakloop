# Tasks: Agent Context Overhaul

**Input**: Design documents from `/specs/014-agent-context-overhaul/`
**Prerequisites**: plan.md, spec.md (6 clarifications), research.md (B1–B14, O1–O18, D1–D10), audit/claim-audit.md, contracts/context-layer.md

**Organization**: one file per task. Every rewrite task means: fix/delete every stale
claim listed for that file in `audit/claim-audit.md`, add only missing-coverage items
that encode invariants, de-duplicate per the O-map (owner keeps the rule, others get a
one-hop pointer), keep the file ≤200 lines (target ≤70 for modules), follow the
contract in `contracts/context-layer.md`. Cite nothing from memory — every claim must
have been verified in the audit or re-verified against code while writing.

## Phase 1: Setup

*(none — no project scaffolding needed; audit + ownership map already exist as
research artifacts from /speckit-plan)*

## Phase 2: Foundational

- [ ] T001 Write the line-budget guard test in `tests/integration/test_context_file_budget.py`: discover every git-tracked CLAUDE.md (`git ls-files '*CLAUDE.md'` with `Path.rglob` fallback excluding `.venv`), assert each ≤200 lines, failure message names the offending file + count. Stdlib + pytest only. NOTE: lands in the same commit as T002 so the suite is green at every commit (root is currently 298 lines).

## Phase 3: User Story 1 — Accurate, lean root CLAUDE.md (P1) 🎯 MVP

**Goal**: root file ≤200 lines, every sentence code-true, guide anatomy B3.
**Independent test**: guard test passes; every claim traceable to audit evidence; six smoke tasks routable from root alone.

- [ ] T002 [US1] Rewrite `CLAUDE.md` (root): SPECKIT block (markers kept; 014 active ≤10 lines; 001–013 one line each) · overview · tech stack fixed list (add json-repair; flag readchar phantom dep) · 19-module layout table with corrected dependency edges (audit R4–R9) · commands · conventions (3–7 per area, schema_version owner O3, engine-import owner O1) · traps (corrected citations R3/R10/R11; torchaudio O2; keyboard-consolidation reality R2; scipy divergence D8; one-line pointers for O6/O13) · never-do list (incl. anti-rot line pointing at constitution O16) · maintenance ≤5 lines · pointers (specs range R12). Commit together with T001; run `uv run pytest tests/integration/test_context_file_budget.py -q` + full suite.

## Phase 4: User Story 2 — Nested per-module CLAUDE.md files (P2)

**Goal**: each module file holds only verified local invariants/extension points/gotchas; zero duplicated rules.
**Independent test**: per-file audit fixes applied; duplicate-rule grep resolves to single owners; all ≤200 lines.

- [ ] T003 [P] [US2] Rewrite `src/speakloop/llm/CLAUDE.md` (fix L1; owner of O5, O13; add per-class `parallel_safe` convention, STRIPPED_ENV_VARS set, DEFAULT_TIMEOUT/claude_timeout_seconds, `_status_run` second-spawner note, CLAUDE_TIER_MAP pointer to cli)
- [ ] T004 [P] [US2] Rewrite `src/speakloop/cli/CLAUDE.md` (fix C1–C6; add today/rebuild/resume, `resolve_engine_choice` precedence + `EngineSelectionError`, CLAUDE_TIER_MAP + `_build_runners`, listen-loop divergence note)
- [ ] T005 [P] [US2] Rewrite `src/speakloop/sessions/CLAUDE.md` (fix S1–S7; owner of O6; document `_BackgroundAsr` single daemon worker, key surface per stage, Runners/SessionResult, budgets, RawKeyReader re-entrancy)
- [ ] T006 [P] [US2] Rewrite `src/speakloop/audio/CLAUDE.md` (fix A1; add scipy divergence trap A2, PlaybackError/RecorderError, retry constants, lazy abort import rationale)
- [ ] T007 [P] [US2] Rewrite `src/speakloop/asr/CLAUDE.md` (fix AS1–AS4; point to root for O2; add decode-guard constants + `_is_degenerate`, EngineSelection fields, pre-warm note)
- [ ] T008 [P] [US2] Rewrite `src/speakloop/feedback/CLAUDE.md` (fix F1–F4; owner of O4; add `_strip_code_fences`, 4-rung ladder, `SPEAKLOOP_DEBUG_LLM`, `next_available_path`, timings kwargs, 013 note on openrouter_prompt_default.txt; point to rules/llm-calls.md for O7/O8)
- [ ] T009 [P] [US2] Rewrite `src/speakloop/metrics/CLAUDE.md` (fix M1–M5 — all dict returns + vad_regions kwargs; add FILLER_TOKENS/REPAIR_MARKERS/PAUSE_THRESHOLD_MS as named constants)
- [ ] T010 [P] [US2] Rewrite `src/speakloop/trends/CLAUDE.md` (fix T1–T3; add ReadResult/iter_reports/format_series, pattern_series + 4th table (010), flat-glob + silent-skip invariants, METRIC_KEYS)
- [ ] T011 [P] [US2] Rewrite `src/speakloop/triage/CLAUDE.md` (add named threshold constants, LRU phantom-phrase cache, TriageResult.summary, follow-up-path usage, module-level import note; point to rules/llm-calls.md)
- [ ] T012 [P] [US2] Rewrite `src/speakloop/coverage/CLAUDE.md` (add MIN_POINTS soft-bound reality, CoverageResult/star_key_points, resume consumer; keep ideal-answer-IS-passed note as pointer to rules/llm-calls.md owner)
- [ ] T013 [P] [US2] Rewrite `src/speakloop/interviewer/CLAUDE.md` (fix I1 ValueError; add I2 012-reorder fact, temperature/max-tokens constants, `_is_grounded` detail, s-key handled in coordinator)
- [ ] T014 [P] [US2] Rewrite `src/speakloop/srs/CLAUDE.md` (fix SR1 resume consumer; add grammar-fallback thresholds, `_NEW_GRADE_RANK=2.5` position, capacity floor)
- [ ] T015 [P] [US2] Rewrite `src/speakloop/store/CLAUDE.md` (fix ST1–ST4 — rebuild does NOT restore next_due, no srs import, follow-up patterns not folded, fsync; point to sessions for O6 main-thread-write rule)
- [ ] T016 [P] [US2] Rewrite `src/speakloop/warmup/CLAUDE.md` (add tuning constants, judge substring-matching surprise, per-item budget lives in coordinator, load_drill_prompt return type)
- [ ] T017 [P] [US2] Rewrite `src/speakloop/tts/CLAUDE.md` (fix TT1; add purge()/cache function surface, SPEAKLOOP_TTS_CACHE_DIR override, DEFAULT_VOICE/SPEED)
- [ ] T018 [P] [US2] Rewrite `src/speakloop/installer/CLAUDE.md` (add ValidationResult fields, SIZE_TOLERANCE, phase model-list constants; trim restated rules per O-map)
- [ ] T019 [P] [US2] Rewrite `src/speakloop/config/CLAUDE.md` (fix CF1–CF4; owner of O10; add full loop_config.py entry + loop.yaml key table from research, SPEAKLOOP_* env overrides, 010 path functions, XDG note)
- [ ] T020 [P] [US2] Rewrite `src/speakloop/content/CLAUDE.md` (add Question.type + _VALID_TYPES (010-P5), QAFile.warnings, schema limits, kebab-case ids)
- [ ] T021 [P] [US2] Rewrite `src/speakloop/debrief/CLAUDE.md` (fix DB1–DB2; add console/read_key injectables, KeyboardSkip, arrow-key menu, ANNOUNCEMENT_LINE)

## Phase 5: User Story 3 — Scoped rules and hygiene (P3)

- [ ] T022 [US3] Create `.claude/rules/testing.md` with frontmatter `paths: ["tests/**"]` — owner of O9: never touch real claude binary/mic/keyboard/live models; injected fakes only (FakeKeyReader, fake Runner, fake record_fn); cached fixtures; repro-gate skips; ≤60 lines.
- [ ] T023 [US3] Create `.claude/rules/llm-calls.md` with frontmatter `paths` covering `src/speakloop/{feedback,coverage,interviewer,triage,warmup}/**` — owner of O7 (ideal_answer boundary, with the three legitimate exceptions) and O8 (degradation contract); ≤60 lines.
- [ ] T024 [US3] Fix the 4 factual stale claims in `README.md` (audit D1–D4) — report filename pattern, Persian-L1 catalog invite, "version-pinned" wording, License heading structure. No marketing rewrite.

## Phase 6: User Story 4 — Anti-rot convention (P4)

- [ ] T025 [US4] Amend `.specify/memory/constitution.md`: add anti-rot Development Guideline ("any commit that changes behavior MUST update the owning context file in the same commit"), bump version 1.0.0 → 1.1.0, update Sync Impact Report header per Governance.

## Phase 7: Polish & verification

- [ ] T026 Run six fresh-subagent smoke tests (task text only, no history): (1) add a new LLM analysis call — where + rules; (2) add a new session-report frontmatter key safely; (3) engine selection precedence; (4) what must tests never do; (5) add a new CLI flag to practice; (6) where is TTS cached + when does it invalidate. Record verdict + evidence each in `specs/014-agent-context-overhaul/audit/smoke-tests.md`.
- [ ] T027 Verify memory loading (/memory equivalent: enumerate launch-loaded files per documented rules) and record in `specs/014-agent-context-overhaul/audit/smoke-tests.md`.
- [ ] T028 Diff-scope guard + full suite: `git diff --name-only main...HEAD` confined to `*.md`, `.claude/**`, `specs/014-*/**`, guard test; `uv run pytest -q` = 696 passed baseline + 1 new (697), 3 skipped, 2 deselected. Record numbers.
- [ ] T029 Write `RETURN_REPORT.md` at repo root: before/after inventory (lines + tokens), claim-audit table pointer + verdict counts, rule-ownership map, smoke verdicts, suite numbers, merge readiness, Blocked section if any.
- [ ] T030 Adversarial context-accuracy review (time permitting): reviewer subagent hunts for remaining claims contradicting code across all rewritten files; fix findings; update RETURN_REPORT.md.

## Dependencies

- T001+T002 land together (same commit) and block everything (root is the O-map anchor).
- T003–T021 all parallel [P] after T002; reference owners established by T002/T022/T023 — write pointers assuming rules files exist; T022/T023 may land in the same phase push.
- T024 independent after T002. T025 after T002 (root never-do line references it).
- T026–T030 strictly after all prior phases.

## Implementation strategy

Commit/push per phase: (1) T001+T002, (2) T003–T021, (3) T022–T024, (4) T025,
(5) T026–T030. Diff-scope guard checked at every commit. MVP = Phase 3.
