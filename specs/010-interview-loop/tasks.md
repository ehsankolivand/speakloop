---
description: "Task list for Interview Loop (010)"
---

# Tasks: Interview Loop

**Input**: Design documents from `specs/010-interview-loop/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests policy (per request)**: automated tests are written **only for deterministic logic** — SRS
scheduling math, coverage parse/aggregate/delta, triage classification, consistency-checker resolution,
store rebuild, schema parsing, report round-trip — as **table-driven pytest cases with recorded
fixtures**. **No byte-exact golden-file assertions.** The regenerated sample reports
(`tests/fixtures/reports/sample-*.md`) are committed **as human diff aids only**, never asserted
byte-for-byte. Voice/interactive behavior (TTS pronunciation, follow-up latency, silence/timeout) is
covered by **explicit manual smoke-test checklists**, not automated tests.

**Organization**: by user story. Per request, the **transcript-triage** and **consistency-check**
components of the trustworthy-feedback story (US4) are pulled into **Foundational** because every other
story's analysis depends on them; US4's own phase only **wires** results into the report and validates
the guarantees.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no dependency on an incomplete task)
- **[Story]**: US1–US5 (Foundational/Setup/Polish tasks carry no story label)

## Path conventions

Single project: `src/speakloop/`, `tests/` at repo root (per plan.md). Each task is scoped to one file
where possible. **Shared files edited across phases** — `sessions/coordinator.py`,
`feedback/report_builder.py`, `cli/practice.py` — are edited **sequentially** (not in parallel); the
stories stay independently *shippable/testable* because each phase leaves the system working.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: scaffolding that later phases build on; no behavior change yet.

- [X] T001 [P] Create the six new module skeletons (dir + `__init__.py` + a one-paragraph `CLAUDE.md` stub each) for `src/speakloop/{interviewer,triage,coverage,srs,warmup,store}/` (Principle IV — each module ships a CLAUDE.md)
- [X] T002 [P] Create labeled-fixture directories `tests/fixtures/{triage,coverage,store}/` each with a `README.md` stating the labeling rubric (authored from real prior sessions, independent of the implementation)
- [X] T003 [P] Extend `tests/fixtures/transcripts/gold_set.yaml` with labeled cases: ASR hallucinations (silence phantoms), pronunciation mishearings (e.g. must→mouse), and content errors (e.g. "Android 11" vs ideal "Android 12")
- [X] T004 [P] Add new path helpers in `src/speakloop/config/paths.py`: `store_path()`, `loop_config_path()`, and the seeded prompt-file paths (`openrouter_followups_prompt`, `_keypoints_`, `_coverage_`, `_triage_`, `_drill_`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: no user story can begin until this phase is complete. Includes the triage + consistency
components (per request) since every story's analysis depends on them, plus the ASR-signal surfacing,
the derived store, the additive frontmatter, the report-section scaffold, the one-engine runner bundle,
and the graceful-degradation contract.

### ASR signals + metrics (prereq for triage & real-speech metrics)

- [X] T005 Surface decode signals on the transcript dataclasses in `src/speakloop/asr/interface.py`: add `WordTiming.probability`, new frozen `SegmentMeta`, and `Transcript.segments`/`Transcript.vad_regions` (all additive optional, defaulted so existing call sites + Parakeet path are unchanged)
- [X] T006 Populate the new fields in `src/speakloop/asr/whisper_mlx_engine.py` `_result_to_transcript` (extract per-segment `avg_logprob`/`no_speech_prob`/`compression_ratio`, per-word `probability`, and attach the Silero VAD regions)
- [X] T007 Add optional `vad_regions=None` to `compute_all` in `src/speakloop/metrics/__init__.py` (compute over real-speech spans when present; **byte-identical** to today when `None`)
- [X] T008 [P] Add optional real-speech-duration param in `src/speakloop/metrics/speech_rate.py` (denominator = real-speech duration when supplied; unchanged default)
- [X] T009 [P] Add optional real-speech-regions param in `src/speakloop/metrics/pauses.py` (filter inter-word gaps to within speech regions; unchanged default)

### Triage + consistency (foundational per request)

- [X] T010 [P] Add the phantom-phrase data file `src/speakloop/triage/phantom_phrases.txt` (known Whisper silence hallucinations: "thank you", "I'll see you later", subtitle/subscribe boilerplate)
- [X] T011 Implement the **deterministic** hallucination filter in `src/speakloop/triage/hallucination.py` (drop spans on VAD-silence overlap, `no_speech_prob ≥ 0.6`, `avg_logprob ≤ −1.0`, `compression_ratio ≥ 2.4`, or phantom-list match — runs BEFORE grammar; no LLM)
- [X] T012 [P] Add the triage system prompt default `src/speakloop/triage/triage_prompt_default.txt` (mishearing classification instructions + strict-JSON contract per contracts/llm-calls.md C4)
- [X] T013 Implement the LLM mishearing classifier in `src/speakloop/triage/mishearing.py` (injected `LLMEngine` + reuse `grammar_analyzer._extract_json`; returns pronunciation-flag spans; **skipped** when no LLM — never raises into the loop)
- [X] T014 Implement the artifact consistency checker in `src/speakloop/triage/consistency.py` (verdict JSON via `_extract_json`; apply `fix` or `drop`; **withhold** the artifact on `LLMEngineError` per C5)
- [X] T015 [P] Write `src/speakloop/triage/CLAUDE.md` (purpose, public interface, deps = injected LLMEngine + asr Transcript, consumers = coordinator/practice)

### Derived store + rebuild

- [X] T016 [P] Implement store dataclasses + `store_version` in `src/speakloop/store/model.py`
- [X] T017 Implement JSON `load(path)` + `save_atomic(path, store)` (stdlib `json` + `os.replace`) in `src/speakloop/store/io.py`
- [X] T018 Implement `rebuild(sessions_dir) -> Store` (fold session reports → schedule/key_points/patterns) in `src/speakloop/store/rebuild.py`
- [X] T019 [P] Write `src/speakloop/store/CLAUDE.md`
- [X] T020 Add the `speakloop rebuild` delegate in `src/speakloop/cli/rebuild.py` and register it in `src/speakloop/cli/main.py` (lazy imports; loads no engines)

### Frontmatter + report scaffold + runner bundle + degradation

- [X] T021 Add the additive-optional `Session` fields (`question_type`, `warmup`, `follow_ups`, `coverage`, `content_errors`, `pronunciation_flags`, `key_points`, `answer_grade`, `analysis_pending`, `triage_summary`) + their `dump`/`parse` round-trip in `src/speakloop/feedback/frontmatter.py` (**`schema_version` stays 1**)
- [X] T022 Add the section-dispatch scaffold in `src/speakloop/feedback/report_builder.py` (render new sections only when present; fixed order grammar → warm-up → coverage → content-errors → pronunciation-flags → follow-ups → type-guidance → transcripts; absent data ⇒ byte-identical to a pre-feature report)
- [X] T023 Generalize engine construction into ONE runner bundle in `src/speakloop/cli/practice.py` (build the `--cloud`/local engine **once**; wire existing grammar+coach; provide an extensible bundle for the new runners; keep engine imports function-local)
- [X] T024 Add the pre-grammar **triage hook** + real-speech metrics wiring + **graceful degradation** in `src/speakloop/sessions/coordinator.py` (run hallucination filter before `grammar_analyzer`; call `compute_all(vad_regions=real_regions)`; on any analytic `LLMEngineError` save audio+transcripts, set `analysis_pending`, write deterministic report, never crash)

### Foundational deterministic tests

- [X] T025 [P] Table-driven test of the hallucination filter on **real-transcript fixtures** in `tests/unit/triage/test_hallucination.py` (asserts silence phantoms dropped, real speech kept — recorded fixtures, no golden file)
- [X] T026 [P] Table-driven test of consistency resolution (apply-fix / drop / withhold-on-error) on recorded verdict fixtures in `tests/unit/triage/test_consistency.py`
- [X] T027 [P] Test store rebuild from sample sessions in `tests/unit/store/test_rebuild.py` (fixtures → expected schedule/patterns; rebuild idempotent; recovers from missing file)
- [X] T028 [P] Back-compat test: every existing `tests/fixtures/sessions/*.md` still parses after the frontmatter additions in `tests/integration/test_schema_backcompat.py` (SC-012)

**Checkpoint**: ASR signals, triage, consistency, store, frontmatter, report scaffold, runner bundle,
and degradation are ready — user-story work can begin.

---

## Phase 3: User Story 1 - Interactive interviewer / follow-ups (Priority: P1) 🎯 MVP

**Goal**: After the final attempt, speak 1–2 unscripted follow-ups grounded in the learner's own words;
answer by voice (~60 s, repeat/skip/timeout); show them in a Follow-ups report section.

**Independent Test**: run a session to the last attempt on today's system; verify a spoken follow-up
references a content word the learner used (or names a gap), is not a bank question, records a voice
answer under budget, and appears in the report with grammar/fluency feedback (spec US1 acceptance + SC-010).

- [X] T029 [P] [US1] Add the follow-up system prompt default `src/speakloop/interviewer/followups_prompt_default.txt` (grounded-probe instructions + strict-JSON contract per C1)
- [X] T030 [US1] Implement follow-up generation + probe-worthiness gate in `src/speakloop/interviewer/followups.py` (injected `LLMEngine` + `_extract_json`; ≥30 real-speech words gate; 1–2 grounded follow-ups; post-parse check that each references a transcript content word or a missed point; raises `LLMEngineError`)
- [X] T031 [P] [US1] Write `src/speakloop/interviewer/CLAUDE.md`
- [X] T032 [US1] Wire the follow-up runner into the bundle + add `--no-followups` in `src/speakloop/cli/practice.py`
- [X] T033 [US1] Add the follow-up stage after attempt 3 in `src/speakloop/sessions/coordinator.py` (warm the model during attempt-3 recording for latency; speak via TTS; record ~60 s honoring repeat/skip/silence-timeout; transcribe + per-attempt analysis; store as `Session.follow_ups`; follow-ups never spawn follow-ups)
- [X] T034 [US1] Render the Follow-ups section in `src/speakloop/feedback/report_builder.py` (per follow-up: question, answer transcript or "no answer — timed out", grammar/fluency feedback; no coverage)
- [X] T035 [P] [US1] Manual smoke-test checklist `specs/010-interview-loop/manual-tests/us1-followups.md` — verify by ear/stopwatch: **follow-up latency ≤ ~10 s** after attempt-3 end; **TTS pronunciation** of technical terms (e.g. `onSaveInstanceState`, `ViewModelStore`, `ANR`); **silence → timeout** records unanswered and continues; **repeat** replays once without consuming budget; **skip** works
- [X] T036 [US1] Update report rendering + regenerate the sample report `tests/fixtures/reports/sample-us1-followups.md` (diff aid showing the Follow-ups section — not a byte-exact golden)

**Checkpoint**: US1 is the MVP — a complete interactive session end to end.

---

## Phase 4: User Story 2 - Cross-session memory, scheduling, warm-up (Priority: P2)

**Goal**: per-pattern trends in every report + a stats view; spaced-repetition scheduling with a
`today` due queue; a 30–60 s warm-up drill with immediate per-item pass/fail.

**Independent Test**: with ≥2 past reports, verify the report shows a numeric per-pattern trend and
`today` lists due questions in priority order (poor ones within 1–2 days); a session opens with a spoken
warm-up reporting pass/fail per item (spec US2 acceptance + SC-005/SC-011). Uses the grammar+fluency
grade fallback until P3 lands.

- [ ] T037 [P] [US2] Implement the answer-quality grade (coverage-primary with grammar+fluency fallback) in `src/speakloop/srs/grade.py`
- [ ] T038 [P] [US2] Implement the interval ladder + mastery/demotion transitions in `src/speakloop/srs/schedule.py`
- [ ] T039 [P] [US2] Implement due-queue priority ordering + capacity/carry-forward + non-empty-while-below-mastery in `src/speakloop/srs/queue.py`
- [ ] T040 [P] [US2] Write `src/speakloop/srs/CLAUDE.md`
- [ ] T041 [P] [US2] Add the drill system prompt default `src/speakloop/warmup/drill_prompt_default.txt` (3-item drill, strict-JSON per C6)
- [ ] T042 [US2] Implement drill generation + the **deterministic** pass/fail/incomplete judge in `src/speakloop/warmup/drill.py`
- [ ] T043 [P] [US2] Write `src/speakloop/warmup/CLAUDE.md`
- [ ] T044 [US2] Add per-pattern occurrence time-series (window N=3, chronological, zero-fill, single-point-no-arrow) in `src/speakloop/trends/aggregator.py`
- [ ] T045 [US2] Render the per-pattern trend series (the FR-009 "stats" view, one command) in `src/speakloop/trends/renderer.py`
- [ ] T046 [P] [US2] Implement the loop-config YAML loader (daily capacity default 5, warm-up/follow-up defaults) in `src/speakloop/config/loop_config.py`
- [ ] T047 [US2] Add the `speakloop today` due-queue command in `src/speakloop/cli/today.py` and register it in `src/speakloop/cli/main.py` (read-only; loads no engines; empty-queue messaging)
- [ ] T048 [US2] Wire the drill runner + warm-up stage before attempt 1 + post-report grade/schedule/store write in `src/speakloop/sessions/coordinator.py` (grade the session, update the `ScheduleEntry`, save the store atomically; `--no-warmup`; skip warm-up gracefully when no qualifying error or generation unavailable)
- [ ] T049 [US2] Render the Warm-up section + per-pattern trend lines in the grammar section in `src/speakloop/feedback/report_builder.py`
- [ ] T050 [P] [US2] Table-driven test of SRS scheduling math (poor→1d, fair→2d, good→×2, strong→×2.5, cap 21, mastery=2-strong, demotion) in `tests/unit/srs/test_schedule.py`
- [ ] T051 [P] [US2] Table-driven test of due-queue priority + capacity carry-forward + non-empty-while-below-mastery + cold-start ranking in `tests/unit/srs/test_queue.py`
- [ ] T052 [P] [US2] Table-driven test of grade banding (coverage-primary + grammar/fluency fallback) in `tests/unit/srs/test_grade.py`
- [ ] T053 [P] [US2] Test the per-pattern trend series (window length, zero-fill, single-point) in `tests/unit/trends/test_pattern_series.py`
- [ ] T054 [P] [US2] Manual smoke-test checklist `specs/010-interview-loop/manual-tests/us2-warmup.md` — verify by ear: warm-up speaks 3 items with **immediate** pass/fail; **TTS pronunciation** of generated drill sentences; `today` ordering reads sensibly
- [ ] T055 [US2] Update report rendering + regenerate the sample report `tests/fixtures/reports/sample-us2-memory.md` (warm-up + trend lines visible in diff)

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Content coverage scoring (Priority: P3)

**Goal**: 5–7 key points per ideal answer (hash-versioned), covered/partial/missed per attempt with the
first→final delta, and content errors separate from grammar. Upgrades the grade to coverage-primary.

**Independent Test**: on a question with known key points, omit one and state one fact wrong; verify the
report shows per-attempt coverage with the delta and lists the wrong fact as a content error separate
from grammar (spec US3 acceptance + SC-004/SC-009).

- [ ] T056 [P] [US3] Add the key-point prompt default `src/speakloop/coverage/keypoints_prompt_default.txt` (5–7 / STAR-4, strict-JSON per C2)
- [ ] T057 [P] [US3] Add the coverage prompt default `src/speakloop/coverage/coverage_prompt_default.txt` (per-attempt coverage + content-errors, strict-JSON per C3)
- [ ] T058 [US3] Implement key-point derivation + ideal-answer hash versioning in `src/speakloop/coverage/keypoints.py`
- [ ] T059 [US3] Implement coverage scoring (parse/validate, aggregate = (covered+0.5·partial)/N, round delta) in `src/speakloop/coverage/scoring.py`
- [ ] T060 [US3] Implement content-error detection (mutually-exclusive only; omissions/extra-correct excluded) in `src/speakloop/coverage/content_errors.py`
- [ ] T061 [P] [US3] Write `src/speakloop/coverage/CLAUDE.md`
- [ ] T062 [US3] Wire the key-points + coverage runners into the bundle in `src/speakloop/cli/practice.py`
- [ ] T063 [US3] Add coverage scoring per session + key-point cache-by-hash + upgrade the grade to coverage-primary in `src/speakloop/sessions/coordinator.py` (derive/load key points by `(question_id, ideal_answer_hash)`; store `key_points`+version in `Session`; feed coverage into `grade_session`)
- [ ] T064 [US3] Render the Coverage (per-attempt + first/final delta) and Content-errors sections in `src/speakloop/feedback/report_builder.py`
- [ ] T065 [P] [US3] Table-driven test of coverage parse/aggregate/delta + version guard (no cross-version delta) on recorded LLM-response fixtures in `tests/unit/coverage/test_scoring.py`
- [ ] T066 [P] [US3] Table-driven test of key-point matching against fixture transcripts + hash-change re-derivation in `tests/unit/coverage/test_keypoints.py`
- [ ] T067 [P] [US3] Table-driven test of content-error detection (flags mutually-exclusive, ignores omissions/extra-correct) on recorded fixtures in `tests/unit/coverage/test_content_errors.py`
- [ ] T068 [US3] Update report rendering + regenerate the sample report `tests/fixtures/reports/sample-us3-coverage.md`

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 - Trustworthy pipeline (wire + validate) (Priority: P4)

**Goal**: the triage + consistency machinery (built in Foundational) is wired into the report and proven:
mishearings appear only as pronunciation flags, hallucinations never reach grammar evidence, and every
generated artifact is consistency-checked before write.

**Independent Test**: feed a transcript with a known silence hallucination and a known mishearing; verify
the hallucination is in no grammar/metric/coverage output and the mishearing appears only in Pronunciation
flags; seed an artifact contradiction and verify it is corrected/dropped before write (SC-003/SC-004/SC-006).

- [ ] T069 [US4] Wire the mishearing runner into the bundle + invoke the consistency check on every generated artifact (drill sentences; cloud coach's improved answer + flashcards) before write in `src/speakloop/cli/practice.py`
- [ ] T070 [US4] Render the Pronunciation-flags section and ensure content-errors render separate from grammar in `src/speakloop/feedback/report_builder.py`
- [ ] T071 [US4] Finalize coordinator wiring in `src/speakloop/sessions/coordinator.py` (attach mishearing flags + `triage_summary` to `Session`; pass real-speech regions to metrics; invoke consistency before report write)
- [ ] T072 [P] [US4] Table-driven test: mishearing classification on recorded fixtures (must→mouse) → pronunciation flags, never grammar, in `tests/unit/triage/test_mishearing.py`
- [ ] T073 [P] [US4] Validation test: 0 hallucination spans in grammar evidence (SC-003) and 0% mishearings counted as grammar (SC-006) over the labeled `gold_set.yaml` + `tests/fixtures/triage/` in `tests/integration/test_triage_guarantees.py`
- [ ] T074 [P] [US4] Validation test: a seeded artifact contradiction is corrected or dropped before the report is written (SC-004) in `tests/integration/test_artifact_consistency.py`
- [ ] T075 [P] [US4] Manual smoke-test checklist `specs/010-interview-loop/manual-tests/us4-triage.md` — verify by ear: a real mishearing surfaces as a pronunciation flag (not a grammar "missing verb"); a silence hallucination never appears in feedback
- [ ] T076 [US4] Update report rendering + regenerate the sample report `tests/fixtures/reports/sample-us4-pronunciation.md`

**Checkpoint**: US1–US4 independently functional; feedback is trustworthy.

---

## Phase 7: User Story 5 - Question-type expansion (Priority: P5)

**Goal**: behavioral/STAR and hypothetical question types with type-specific report guidance; type-aware
key points; all types keep the 4/3/2 structure.

**Independent Test**: add one behavioral and one hypothetical question; verify the behavioral report shows
which of S/T/A/R were present and the hypothetical shows conditional/future-form guidance citing the
learner's clauses; definition questions unchanged (spec US5 acceptance + SC-008).

- [ ] T077 [US5] Add the additive-optional `type` field + validation (default `definition`; loader accepts it; question-file `schema_version` unchanged) in `src/speakloop/content/schema.py`
- [ ] T078 [P] [US5] Add one behavioral/STAR and one hypothetical example question to `content/questions.yaml`
- [ ] T079 [US5] Make key-point derivation type-aware (4 STAR components for behavioral; 5–7 otherwise) in `src/speakloop/coverage/keypoints.py`
- [ ] T080 [US5] Render the STAR-structure check + conditional/future-form guidance sections in `src/speakloop/feedback/report_builder.py`
- [ ] T081 [US5] Route `question_type` into the session + set the type-specific final-round goal (behavioral = all STAR components within the time budget) in `src/speakloop/sessions/coordinator.py`
- [ ] T082 [P] [US5] Table-driven test of `type` parsing/default/validation in `tests/unit/content/test_type_field.py`
- [ ] T083 [P] [US5] Manual smoke-test checklist `specs/010-interview-loop/manual-tests/us5-types.md` — verify a behavioral answer's STAR check reads correctly and a hypothetical's conditional guidance is on-point
- [ ] T084 [US5] Update report rendering + regenerate the sample report `tests/fixtures/reports/sample-us5-types.md`

**Checkpoint**: all five stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T085 Implement `speakloop resume` for analysis-pending sessions in `src/speakloop/cli/resume.py` + register in `src/speakloop/cli/main.py` (re-run the missing analysis over preserved transcripts; clear `analysis_pending`; update the store; `--cloud` selects the engine)
- [ ] T086 Add `doctor` rows in `src/speakloop/cli/doctor.py` (derived-store presence/version + rebuildable check; the five seeded prompt files; loop-config YAML)
- [ ] T087 [P] Update the root `CLAUDE.md` module map/table with the six new modules (architecture + pointers; Principles IV/XI)
- [ ] T088 [P] Full report round-trip test (`dump → parse → dump` idempotent with all new fields populated) in `tests/integration/test_report_roundtrip.py`
- [ ] T089 [P] Daily-loop end-to-end integration test with stubbed engines (due-selection → warm-up → 3 attempts → follow-ups → report; then `rebuild`; then `resume` on a pending session) in `tests/integration/test_daily_loop.py`
- [ ] T090 Manual end-to-end smoke test `specs/010-interview-loop/manual-tests/daily-loop.md` — run the full loop by voice locally and with `--cloud`; confirm `today`, `trends`, `rebuild`, `resume`, and `quickstart.md` steps; record results

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → depends on Setup; **blocks all user stories**.
- **User stories (P3–P7)** → all depend on Foundational; otherwise independent increments.
- **Polish (P8)** → depends on the stories whose surface it touches (resume needs the analytic calls; doctor needs the store/prompts).

### Cross-story shared-file ordering (not parallel)

- `sessions/coordinator.py`: T024 (Found.) → T033 (US1) → T048 (US2) → T063 (US3) → T071 (US4) → T081 (US5).
- `feedback/report_builder.py`: T022 (Found.) → T034 (US1) → T049 (US2) → T064 (US3) → T070 (US4) → T080 (US5).
- `cli/practice.py`: T023 (Found.) → T032 (US1) → T062 (US3) → T069 (US4).
- `cli/main.py`: T020 (rebuild) → T047 (today) → T085 (resume) register sequentially.

### Within each story

- Prompt-default + module-logic + module CLAUDE.md (mostly [P]) → bundle wiring (practice.py) → coordinator stage → report rendering → deterministic tests [P] → sample-report regen.

### Parallel opportunities

- Setup: T001–T004 all [P].
- Foundational: T008/T009 [P]; T010/T012/T015 [P]; T016/T019 [P]; T025/T026/T027/T028 [P] (after their targets exist).
- Per story, the `[P]` prompt-defaults, CLAUDE.md, and deterministic test tasks run in parallel; the shared-file tasks (coordinator/report_builder/practice) do not.

---

## Parallel Example: Foundational deterministic tests

```bash
# After T011/T014/T018/T021 land, run these together:
Task: "T025 hallucination filter test in tests/unit/triage/test_hallucination.py"
Task: "T026 consistency resolution test in tests/unit/triage/test_consistency.py"
Task: "T027 store rebuild test in tests/unit/store/test_rebuild.py"
Task: "T028 schema back-compat test in tests/integration/test_schema_backcompat.py"
```

## Parallel Example: User Story 2 (SRS)

```bash
# srs is three independent files + three independent tests:
Task: "T037 grade.py"   Task: "T038 schedule.py"   Task: "T039 queue.py"
Task: "T050 test_schedule.py"   Task: "T051 test_queue.py"   Task: "T052 test_grade.py"
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL — triage/consistency/store/frontmatter/scaffold/
   degradation) → 3. Phase 3 US1 → **STOP & VALIDATE**: run the interactive session end to end (T035
   manual checklist), then demo. US1 is a complete, shippable interactive interviewer.

### Incremental delivery

US1 (MVP) → US2 (memory/SRS/warm-up) → US3 (coverage) → US4 (trustworthy wiring + guarantees) → US5
(question types) → Polish (resume, doctor, docs, e2e). Each story leaves the system working and is
independently testable per its checkpoint.

### Test discipline (per request)

- Automated, table-driven, recorded-fixture tests **only** for deterministic logic: T025–T028, T050–T053,
  T065–T067, T072–T074, T082, T088–T089.
- **No byte-exact golden assertions.** Sample reports (`tests/fixtures/reports/sample-*.md`) are diff aids.
- Voice/interactive behavior → manual smoke checklists: T035, T054, T075, T083, T090.

## Notes

- `[P]` = different file, no incomplete-task dependency. `[Story]` maps to spec.md US1–US5.
- Every new module ships its `CLAUDE.md` (T015, T019, T031, T040, T043, T061) — Principle IV gate.
- Every new LLM call reuses the injected `LLMEngine` + the existing `_extract_json` ladder and degrades
  via `analysis_pending` — never a new engine path (Principle V, FR-039).
- `schema_version` stays 1; new frontmatter keys are additive-optional (SC-012).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
