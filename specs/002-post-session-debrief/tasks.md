---
description: "Task list for Post-Session Interactive Debrief"
---

# Tasks: Post-Session Interactive Debrief

**Input**: Design documents from `/specs/002-post-session-debrief/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: INCLUDED — plan.md "Testing" mandates unit tests (catalog, coherence, ranking, narrative/top-priority, frontmatter round-trip, view model, renderer, menu, audio player), a human-labelled gold set under `tests/fixtures/`, and a Phase-C integration test. Live model calls remain forbidden; the LLM is stubbed.

**Organization**: Tasks are grouped by user story (US1–US4) in the plan's shipping order (US1 → US2 → US3 → US4). Each story is an independently testable increment per Constitution Principle XII.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4 — Setup/Foundational/Polish carry no story label
- All paths are repo-relative to the repository root.

## Path Conventions

Single Python project: source under `src/speakloop/`, tests under `tests/`. New module is `src/speakloop/debrief/`; content-quality work stays in `src/speakloop/feedback/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new module skeleton and test scaffolding so later phases have a home. No behaviour yet.

- [X] T001 [P] Create `src/speakloop/debrief/__init__.py` with a public-surface docstring and placeholder re-exports (`DebriefChoice`, `DebriefRunner` / `run` to be filled in US2/US3) per contracts/debrief-interface.py.
- [X] T002 [P] Create `src/speakloop/debrief/CLAUDE.md` documenting the module's single responsibility (post-session render + audio + menu), the Principle V engine-isolation rule (no `kokoro_mlx`/`mlx_audio`/`mlx_lm`/`parakeet_mlx` imports; TTS only via injected `TTSEngine` + `play_fn`), and that `cli/practice.py` is the only intended caller.
- [X] T003 [P] Create test fixture directories `tests/fixtures/transcripts/` and `tests/fixtures/reports/` each with a short `README.md` describing the gold-set contract (transcript → expected pattern labels; sample Session/report shapes).
- [X] T004 [P] Create empty test package dirs `tests/unit/feedback/__init__.py` and `tests/unit/debrief/__init__.py` so pytest collects the new suites.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Additive frontmatter fields that BOTH the content work (US1, which persists them) and the renderer (US2+, which reads them) depend on. `schema_version` stays `1`.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Extend `src/speakloop/feedback/frontmatter.py`: add additive fields `explanation: str`, `impact_rank: int`, `catalog_id: str | None` to `GrammarPattern`; add `corrected: str | None` to the Evidence Quote sub-entity; add top-level `cross_attempt_narrative: str | None` and `top_priority: str | None` to `Session`. All optional/default-empty; `schema_version` MUST remain `1`. Per data-model.md §A.
- [X] T006 Update the YAML (de)serialization in `src/speakloop/feedback/frontmatter.py` so the new fields round-trip and unknown keys are still ignored (forward/back compat); ensure Phase-B reports serialize with `grammar_patterns: []` and may carry fluency-only narrative/top_priority.
- [X] T007 [P] Unit test the additive round-trip in `tests/unit/feedback/test_frontmatter_additive.py`: a Session with the new fields serializes and re-parses identically; a pre-feature report (no new keys) still parses; assert `schema_version == 1`.

**Checkpoint**: Report schema can carry the new fields without breaking existing readers (FR-031). The trends reader is unaffected.

---

## Phase 3: User Story 1 - Trustworthy, actionable feedback content (Priority: P1) 🎯 MVP

**Goal**: The written report is accurate and actionable — catalog-correct labels, verbatim "You said / Better / Because", ASR garble dropped, impact-ranked patterns, and one deterministic Top priority across grammar + fluency.

**Independent Test**: Replay the gold-set transcripts through the analyzer (LLM stubbed). Verify each pattern has a catalog-accurate label, every evidence quote is verbatim and coherent, each fix names the user's words + a concrete correction, patterns are impact-ordered, garble ("Killing RT check") is dropped, and one Top priority is surfaced — visible purely as an improved `.md` report, no UI.

### Data files & catalog loader for US1

- [X] T008 [P] [US1] Author `src/speakloop/feedback/persian_l1_catalog.yaml` from contracts/persian-l1-catalog.yaml: `catalog_version: 1` plus all seed entries (gerund-infinitive-confusion, comparative-form, plural-agreement, article-omission-common, preposition-substitution, 3sg-s-drop, aux-drop, possessor-order) with `id`, `label`, `transfer_reason`, `impact_rank`, `detection_hints`, `examples`, `methodology_ref`.
- [X] T009 [P] [US1] Author `src/speakloop/feedback/common_words.txt`: a compact (~3–5k) high-frequency English wordlist for the coherence filter (FR-006), one word per line, lowercase.
- [X] T010 [US1] Implement `src/speakloop/feedback/catalog.py`: load `persian_l1_catalog.yaml` once at import into frozen dataclasses (`CatalogEntry`, `Catalog`); fail loudly on malformed YAML; expose lookup by `id`/`label` and the fixed open-bucket default `impact_rank` (below all catalog entries). Per research.md §(a), data-model.md §B.
- [X] T011 [P] [US1] Unit test `tests/unit/feedback/test_catalog.py`: catalog loads, all seed ids present, every entry has non-empty `transfer_reason` + `impact_rank`, open-bucket default rank sorts below every catalog rank, malformed YAML raises at load.

### Coherence filter for US1

- [X] T012 [US1] Implement `src/speakloop/feedback/coherence.py`: deterministic ASR-garble filter (FR-006) running AFTER the verbatim-substring check — drop a quote when too few alphabetic tokens or the out-of-wordlist token fraction exceeds threshold, excluding attested technical tokens already present across the transcripts; default to dropping when uncertain (favor precision). Per research.md §(e).
- [X] T013 [P] [US1] Unit test `tests/unit/feedback/test_coherence.py`: "Killing RT check" is dropped; attested jargon ("Kotlin", "coroutine", "dispatcher") is kept; a clean grammatical quote passes; ambiguous → dropped.

### Deterministic narrative & Top priority for US1

- [X] T014 [US1] Implement `src/speakloop/feedback/narrative.py`: deterministic cross-attempt narrative (what improved / stayed the same across 4/3/2, extending the existing `_cross_attempt_paragraph` logic) and a single `top_priority` chosen by the most-impactful-wins rule across grammar patterns (by `impact_rank`) and fluency dimensions (fixed severity heuristic with documented thresholds); degrade to a sensible default when neither is notable. Per research.md §(g), data-model.md §A.3 / §C.
- [X] T015 [P] [US1] Unit test `tests/unit/feedback/test_narrative.py`: a severe grammar pattern wins; a severe fluency issue (e.g. high filler density) wins even when mild grammar patterns exist; empty/silent attempts degrade to the default message; output is deterministic across runs.

### Catalog-aware analyzer + report rendering for US1

- [X] T016 [P] [US1] Create gold-set fixtures in `tests/fixtures/transcripts/`: the documented cases "I like to programming", "eight year experience", "I like my job even bigger than ten years ago", "Killing RT check" (garble), each paired with expected catalog label(s) / expected-drop, for SC-002/SC-003.
- [X] T017 [US1] Rewrite `src/speakloop/feedback/grammar_analyzer.py` to be catalog-aware: inject catalog `detection_hints` into the LLM prompt; emit per-evidence `corrected` ("Better:" line) and `explanation` ("Because:" transfer reason — from catalog for seed patterns, LLM-supplied + verified non-empty/coherent for open-bucket); run the coherence filter; preserve the verbatim-substring guarantee; suppress patterns whose only correction equals the quote (FR-009); assign persisted `impact_rank` and sort ascending by `(impact_rank, -occurrence_count, first_attempt_ordinal)`; open-bucket requires `occurrence_count >= 2` (FR-002). Per contracts GrammarAnalyzer, research.md §(b).
- [X] T018 [US1] Update `src/speakloop/feedback/report_builder.py` to render the new fields into the Markdown body: a "Top priority for next session" section, the cross-attempt narrative, and three-line fixes ("You said / Better / Because") in `impact_rank` order; keep the Phase-B placeholder when grammar is unavailable; handle the "no actionable patterns detected" message when all candidates are dropped.
- [X] T019 [US1] Integration-style unit test `tests/unit/feedback/test_grammar_analyzer.py` (LLM stubbed): feed each gold-set transcript and assert catalog-accurate label, verbatim+coherent evidence, a `corrected` differing from `quote` (per-case), impact-ordered output, garble dropped, and exactly one Top priority surfaced (SC-002 acceptance scenarios 1–6). Additionally, compute the **corrected-coverage ratio** across all reported fixes in the gold set — the fraction of fixes that reference the user's actual words and carry a concrete `corrected` version — and assert it is **≥ 0.8**, directly measuring SC-003.

**Checkpoint**: Running a session produces an accurate, impact-ranked, Top-priority report file — valuable even with no UI changes (US1 MVP complete).

---

## Phase 4: User Story 2 - In-terminal visual debrief with one-keypress replay (Priority: P1)

**Goal**: On session end the report renders in place (banner, three-line cards, trend-coloured table, collapsed transcripts) with an r/n/q + replay/new/quit menu (default replay, arrow nav, `t` transcript toggle); replay returns to the listen phase in < 3 s with no model reload. Works on Phase-B content too.

**Independent Test**: Finish a session (stubbed engines) and confirm in-place render (not raw markdown, no file-path-only output), a prominent Top-priority banner, three-line pattern cards, green/yellow/red trends, collapsed transcripts with "+N words", and a menu accepting r/n/q (and full words). Replay → listen phase same question with no reload; new → picker; quit → shell.

### Coordinator result change (enables debrief from typed data)

- [X] T020 [US2] Change `src/speakloop/sessions/coordinator.py` `run_session(...)` to additionally return the populated in-memory `Session` alongside `report_path` (additive return shape per data-model.md §D); the report is still written exactly as today (FR-015).

### View model & renderer for US2

- [X] T021 [P] [US2] Implement `src/speakloop/debrief/view_model.py`: build `DebriefViewModel` from a `Session` — `is_first_time` (no prior report in `sessions_dir` besides this one), `top_priority`, `narrative`, `attempt_rows` (with `wpm_trend`/`filler_trend` computed first-vs-last with a tolerance band), ranked `pattern_cards`, collapsed `transcript_previews` (first ~10 words + remaining count), `transcripts_expanded=False`, `grammar_available`, and `audio_sections` (ordered narrative → top priority → patterns). Per data-model.md §C.
- [X] T022 [P] [US2] Unit test `tests/unit/debrief/test_view_model.py`: trend enums map correctly (WPM up = improved, filler down = improved, within band = flat); previews collapse with correct remaining-word count; `pattern_cards` sorted by `impact_rank`; `is_first_time` true only when no prior report; `audio_sections` order/count correct.
- [X] T023 [US2] Implement `src/speakloop/debrief/renderer.py` using `rich` (`Live`, `Panel`, `Table`, `Group`, `Text`): bordered Top-priority banner above the patterns (FR-011), three-line cards "You said / Better / Because" in fixed order (FR-012), green/yellow/red trend colouring on the attempt table (FR-013), collapsed-by-default transcripts with "+N words" (FR-014), the `grammar_available=False` placeholder line (FR-028), the first-time orientation line (FR-030), a section-highlight hook + "X of N" progress line (used by US3), and a plain-`console.print` fallback when the terminal reports no control capability. Per research.md §(c).
- [X] T024 [P] [US2] Unit test `tests/unit/debrief/test_renderer.py` capturing a `rich` console: banner present and distinct, cards have the three labelled lines in order, trend cells coloured per direction, transcript shows preview + "+N words", placeholder line appears when grammar unavailable, first-time line appears/absent per flag.

### Menu & orchestrator for US2

- [X] T025 [US2] Implement `src/speakloop/debrief/menu.py`: reuse the existing two-tier tty pattern (`termios`/`tty.setcbreak`, `/dev/tty` fallback, line-buffered fallback for piped input); accept `r`/`n`/`q` and `replay`/`new`/`quit`, default REPLAY, arrow-key navigation (`\x1b[A`/`\x1b[B`), Enter = default; consume `t` internally to toggle `transcripts_expanded` and re-render in place (NOT a `DebriefChoice`), looping until replay/new/quit. Returns `DebriefChoice`. Per research.md §(f), contracts/debrief-interface.py.
- [X] T026 [P] [US2] Unit test `tests/unit/debrief/test_menu.py` (line-buffered/piped input, no real tty): "r"/"replay"/Enter → REPLAY, "n"/"new" → NEW, "q"/"quit" → QUIT, "t" toggles expansion and keeps the menu open (returns only on a terminal choice).
- [X] T027 [US2] Implement `src/speakloop/debrief/debrief.py` orchestrator implementing the `DebriefRunner.run(...)` contract: build view model → render → (audio in US3) → menu → return choice; for US2 it renders + shows the menu (no audio yet). Wire `DebriefChoice`/`run` into `src/speakloop/debrief/__init__.py`.

### CLI replay loop for US2

- [X] T028 [US2] Update `src/speakloop/cli/practice.py`: construct all engines once before the loop; hoist `ParakeetEngine` construction out of `run_session` and inject it every call (research.md §d); loop listen → `run_session` → debrief → menu; on REPLAY re-enter for the same question with NO reload / no doctor / no progress UI (FR-025/FR-026), on NEW open the question picker, on QUIT return to the shell; reset transcript-expansion state each replay; each replay writes a distinct (disambiguated) report.
- [X] T029 [US2] Integration test `tests/integration/phase_c_debrief_test.py` (stubbed resident engines): full session → report written → debrief renders → menu choice REPLAY loops back to the listen phase for the same question with no model reload; verify a distinct report per replay (SC-004 path, no-reload assertion).

**Checkpoint**: The loop closes in-terminal on Phase-B and Phase-C content; replay works with no reload.

---

## Phase 5: User Story 3 - Read-aloud corrections synced to the screen (Priority: P2)

**Goal**: The educational parts (narrative → top priority → ranked patterns' explanation + corrected version) read aloud via the existing TTS engine with a moving highlight and "X of N" progress; announcement line first; any keypress skips to the menu; `--no-audio` skips audio entirely.

**Independent Test**: With audio enabled, confirm the announcement appears, only educational parts are spoken (never transcripts/metrics), the active section is highlighted, "X of N sections" shows, order is narrative → top priority → patterns, and any key skips to the menu. With `--no-audio`, audio is skipped and the menu is immediately reachable.

- [X] T030 [US3] Implement `src/speakloop/debrief/audio_player.py`: synthesize each `AudioSection.speak_text` via the injected `TTSEngine` (+ `play_fn`), reusing the content-addressed TTS cache; advance the renderer's section highlight + "X of N" progress as each plays (FR-019); poll for any keypress to stop remaining audio immediately and return (FR-020); catch any TTS/playback error and return so the menu still appears (FR-029). No engine-specific imports (Principle V). Per research.md §(h).
- [X] T031 [US3] Wire audio into `src/speakloop/debrief/debrief.py`: show the announcement "🔊 Reading your feedback aloud — press any key to skip." (FR-016) then run `audio_player` for the ordered educational sections (FR-017/FR-018) before the menu; treat a keypress during the announcement as a skip; skip the whole audio stage when `no_audio` or `tts_engine`/`play_fn` is None (FR-021).
- [X] T032 [US3] Add the `--no-audio` flag to the `practice` command in `src/speakloop/cli/practice.py` and thread `no_audio` through to `DebriefRunner.run(...)`.
- [X] T033 [P] [US3] Unit test `tests/unit/debrief/test_audio_player.py` (stubbed TTS + play): only educational sections are synthesized (no transcript/metrics text), sections play in narrative → top priority → patterns order, an injected keypress stops remaining audio and returns, and a TTS exception is swallowed so control returns to the menu (FR-017–FR-020, FR-029).

**Checkpoint**: Full audio+visual+menu debrief works; `--no-audio` path verified.

---

## Phase 6: User Story 4 - Graceful degradation and first-time guidance (Priority: P3)

**Goal**: No-LLM → Phase-B debrief with the grammar-placeholder line; TTS failure → visual debrief continues to the menu without hanging; first-time orientation line on the very first debrief only.

**Independent Test**: Disable the grammar model → debrief runs on Phase-B content with the single placeholder line. Force a TTS failure → visual debrief + menu appear immediately. No prior reports → orientation line shows; with prior reports → it does not.

- [X] T034 [US4] Ensure the no-LLM branch in `src/speakloop/debrief/debrief.py` / `view_model.py` sets `grammar_available=False` and renders exactly "Grammar pattern analysis is available when the LLM model is installed." in place of the patterns section, with narrative/top_priority (fluency-only) still shown and audio still reading available educational sections (FR-028).
- [X] T035 [US4] Confirm the first-time orientation line ("This is your feedback. I'll read the key parts aloud, then you can replay this question or pick a new one.") is shown iff `is_first_time` in `src/speakloop/debrief/debrief.py`/`renderer.py`, and is suppressed for returning users (FR-030).
- [X] T036 [P] [US4] Unit test `tests/unit/debrief/test_degradation.py`: grammar-absent Session renders the placeholder line and still reaches the menu; a TTS-raising stub still reaches the menu without hanging (FR-029); first-time vs returning toggles the orientation line (FR-030); SC-007 (always reach the menu) holds for both failure modes.

**Checkpoint**: All four stories functional; the loop never hangs or dead-ends.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, Ctrl+C safety, and end-to-end validation across stories.

- [X] T037 [P] Update `src/speakloop/feedback/CLAUDE.md` to document the new public surface (catalog, coherence, narrative, additive frontmatter fields, report_builder rendering).
- [X] T038 [P] Update `src/speakloop/cli/CLAUDE.md` to note the `--no-audio` flag and the no-reload replay loop.
- [X] T039 Verify Ctrl+C during the debrief (announcement, audio, or menu) returns to the shell cleanly without corrupting the already-written report or leaving temp audio behind (extends FR-016 invariant; edge cases in spec.md).
- [X] T040 Handle the residual edge cases in `view_model.py`/`debrief.py`: all-silent attempts → no fabricated correction; the Top priority renders the exact default "No content captured this session — focus on speaking out loud next time."; zero coherent patterns → the grammar section shows the exact line "No actionable grammar patterns detected this session."; a "Better" identical to "You said" is suppressed not shown (FR-009); narrow/no-colour terminal degrades to readable plain layout.
- [X] T041 Run `specs/002-post-session-debrief/quickstart.md` end-to-end (happy path + degradation paths) and confirm SC-001/SC-004/SC-005/SC-007 hold; record any deviations.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (frontmatter fields are read/written everywhere).
- **US1 (Phase 3)**: Depends on Foundational. No dependency on other stories.
- **US2 (Phase 4)**: Depends on Foundational. Renders US1's persisted fields when present, but is independently testable on Phase-B content (no grammar).
- **US3 (Phase 5)**: Depends on US2 (renderer highlight hook + orchestrator + menu must exist). Builds on US2.
- **US4 (Phase 6)**: Depends on US2 (degradation/onboarding branch the render+menu path); the no-LLM content branch also relies on US1 placeholders.
- **Polish (Phase 7)**: Depends on all targeted stories being complete.

### User Story Dependencies

- **US1 (P1)**: Independent — delivers an improved report file alone.
- **US2 (P1)**: Independent of US1 at runtime (works on Phase-B); needs Foundational.
- **US3 (P2)**: Builds on US2's renderer/menu/orchestrator.
- **US4 (P3)**: Builds on US2 (and US1 placeholder text).

### Within Each User Story

- Tests for a story can be written alongside; the gold-set fixtures (T016) should exist before the analyzer test (T019).
- Data files (catalog, wordlist) before the loaders/filters that read them.
- view_model before renderer before menu before orchestrator.
- Coordinator return change (T020) before the CLI loop (T028) and integration test (T029).

### Parallel Opportunities

- All of Phase 1 (T001–T004) run in parallel.
- US1: T008, T009 (data files) in parallel; T011, T013, T015, T016 are independent test/fixture files; T010/T012/T014 touch separate modules.
- US2: T021 (view_model) and T023 (renderer) are separate files but renderer consumes the view model — write view_model first, then renderer; their tests (T022, T024, T026) are parallel once their targets exist.
- Polish: T037, T038 (separate CLAUDE.md files) in parallel.

---

## Parallel Example: User Story 1

```bash
# Author both in-repo data files together:
Task: "Author src/speakloop/feedback/persian_l1_catalog.yaml (T008)"
Task: "Author src/speakloop/feedback/common_words.txt (T009)"

# Once loaders/filters exist, run their unit tests in parallel:
Task: "Unit test tests/unit/feedback/test_catalog.py (T011)"
Task: "Unit test tests/unit/feedback/test_coherence.py (T013)"
Task: "Unit test tests/unit/feedback/test_narrative.py (T015)"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE**: replay the gold set through the analyzer and confirm accurate, impact-ranked, Top-priority reports (SC-002/SC-003). Ship the improved report file alone.

### Incremental Delivery

1. Setup + Foundational → schema ready.
2. US1 → accurate report file (MVP).
3. US2 → in-terminal render + replay loop (Phase-B and Phase-C).
4. US3 → read-aloud sync + `--no-audio`.
5. US4 → degradation + onboarding.
6. Polish → docs, Ctrl+C safety, quickstart validation.

Each slice leaves a complete working system (Constitution Principle XII); later slices add capability without breaking earlier ones.

---

## Notes

- [P] = different files, no dependency on incomplete tasks.
- LLM is stubbed in all tests; no live model calls (plan.md Testing).
- `schema_version` stays `1`; all frontmatter changes additive (FR-031).
- Engine isolation: `debrief/` imports no engine package — TTS via injected `TTSEngine` + `play_fn` only (Principle V).
- Commit after each task or logical group.
