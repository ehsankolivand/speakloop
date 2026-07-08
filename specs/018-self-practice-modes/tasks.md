# Tasks: Offline Self-Practice Modes — Rescue-Lines Deck & Answer Shadowing

**Input**: Design documents from `specs/018-self-practice-modes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — this repo is test-first for pure logic and CLI commands (mypy-gated modules + `tests/unit/cli/*` with injected fakes). Every source task lists its test task.

**Organization**: By user story. **US1 = `speakloop deck`** (P1, MVP), **US2 = `speakloop shadow`** (P2). The two stories are independent and each ships alone.

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (different file, no dependency on an incomplete task).
- Paths are repo-relative under `src/speakloop/` and `tests/`.

---

## Phase 1: Setup (shared)

- [X] T001 Add the two new pure-logic packages to the mypy gate: append `"src/speakloop/linecards"` and `"src/speakloop/shadowing"` to `[tool.mypy].files` in `pyproject.toml`.
- [X] T002 [P] Create the `linecards` package skeleton: `src/speakloop/linecards/__init__.py` (empty public-API stub) so imports resolve.
- [X] T003 [P] Create the `shadowing` package skeleton: `src/speakloop/shadowing/__init__.py` (empty public-API stub) so imports resolve.

**Checkpoint**: `uv run mypy` still green (empty packages); `uv run python -c "import speakloop.linecards, speakloop.shadowing"` works.

---

## Phase 2: Foundational (blocking prerequisites)

> The two stories share almost no code. The only cross-cutting prerequisite is the shared SRS-ladder helper (US1 needs it; extracting it must keep the existing question scheduler byte-identical). No other foundational work blocks the stories.

- [X] T004 Extract the pure ladder recurrence into `srs.schedule.advance(prev_interval, consecutive_strong, mastered, grade) -> AdvanceResult` (returns `interval_days`, `consecutive_strong`, `mastered`) in `src/speakloop/srs/schedule.py`; refactor `next_due` to compute `prev`, call `advance`, and stamp the `ScheduleEntry` dates — **behavior-preserving**. Keep the ladder constants at the top as the single tuning surface.
- [X] T005 [P] Add a behavior-preserving test in `tests/unit/srs/test_schedule.py` (or new `test_advance.py`) asserting `advance(...)` reproduces `next_due`'s interval/mastery outcomes across poor/fair/good/strong, cap, and mastery-demotion cases; the existing `srs` tests MUST stay green.
- [X] T006 Update `src/speakloop/srs/CLAUDE.md` to document the shared `advance()` helper (public interface + that `next_due` and line-card scheduling both call it; O14 single-tuning-surface note).

**Checkpoint**: `uv run pytest tests/unit/srs -q` green; `uv run mypy` green.

---

## Phase 3: User Story 1 — Rescue-lines deck (`speakloop deck`) — Priority P1 🎯 MVP

**Goal**: A learner drills their own corrected lines (derived from reports) + bundled starter cards in a self-graded hear → say → see → self-mark loop that reschedules on the SRS ladder and persists; plus an offline Anki cloze export.

**Independent test**: With report fixtures containing corrections, `speakloop deck` plays the corrected line before revealing the target and records a self-mark that reschedules the card (persisted across runs); `speakloop deck --export` writes a valid Anki-cloze file. No mic/ASR/report.

### Store section (US1 data)

- [X] T007 [US1] Add the additive default-empty `line_cards: dict[str, dict]` section to `Store` in `src/speakloop/store/model.py` (field + `to_dict`/`from_dict` round-trip; `STORE_VERSION` stays 1) plus small upsert/read helpers for a card's content+state dict (per data-model.md).
- [X] T008 [P] [US1] Add `tests/unit/store/test_line_cards.py`: `line_cards` round-trips through `to_dict`/`from_dict`; a store JSON without the key loads it as `{}` (back-compat).
- [X] T009 [US1] Fold `line_cards` in `src/speakloop/store/rebuild.py`: per report, derive cards from `grammar_patterns[].evidence[]` (skip no-op / missing `corrected`) and insert **content with placeholder SRS state**; extend `tests/unit/store/test_rebuild.py` (or add one) proving a rebuild reproduces the card set with placeholder scheduling.
- [X] T010 [US1] Update `src/speakloop/store/CLAUDE.md`: document `line_cards` (contract, rebuildable-content / live-scheduling trade-off mirroring `pronunciation_contrasts` + `schedule.next_due`).

### `linecards/` pure logic (US1)

- [X] T011 [P] [US1] Implement `LineCard` dataclass + stable `card_id` (`sha1(question_id\x1fquote\x1fcorrected)[:12]`, or `starter:<slug>`) + `derive_cards(reports_dir) -> list[LineCard]` (mirror `trends/reader`: flat `glob("*.md")`, per-file try/except, `feedback.frontmatter.parse`; keep evidence with non-empty `corrected != quote`; dedupe by `card_id`) in `src/speakloop/linecards/cards.py`.
- [X] T012 [P] [US1] Add `tests/unit/linecards/test_cards.py`: derivation from a report fixture yields expected cards; no-op corrections skipped; identical corrections across two reports collapse to one `card_id` (stable identity).
- [X] T013 [P] [US1] Implement `cloze_from_correction(quote, corrected) -> str` (word-level `difflib.SequenceMatcher` diff → wrap changed span in `{{c1::…}}`; degenerate diff → cloze whole corrected) and `to_anki(cards) -> str` (one line per card, trailing `(rule)`) in `src/speakloop/linecards/cloze.py`.
- [X] T014 [P] [US1] Add `tests/unit/linecards/test_cloze.py`: article insertion (`"new instance of it"`→`"a new instance of it"` → `{{c1::a}} …`), verb change (`"system create"`→`"system creates"` → `{{c1::creates}}`), starter card cloze span, and whole-phrase fallback.
- [X] T015 [P] [US1] Implement starter cards: `src/speakloop/linecards/starter_cards.yaml` (≥ 8 English-only interview discourse chunks with `slug`/`text`/`cloze`/`rule`) + `load_starter_cards() -> list[LineCard]` in `src/speakloop/linecards/starter.py`.
- [X] T016 [P] [US1] Add `tests/unit/linecards/test_starter.py`: the bundled YAML loads, has ≥ 8 cards, each with a non-empty `cloze` that is a substring of `text` (so the exporter can wrap it), all English.
- [X] T017 [US1] Implement `advance_card(state, grade, *, today) -> dict` (calls `srs.schedule.advance`, stamps `next_due`/`last_practiced`/`total_reviews`) and `select_due(cards, *, today, capacity) -> list[LineCard]` (never-reviewed OR `next_due <= today`, most-overdue-first ties→lower grade→oldest-practiced, truncated to capacity) in `src/speakloop/linecards/deck.py`. Depends on T004, T011.
- [X] T018 [P] [US1] Add `tests/unit/linecards/test_deck.py`: `again`→due next run at shortest interval; two `easy` marks → mastered/maintenance; due-order priority; capacity truncation; practise-ahead selection when nothing is due.
- [X] T019 [US1] Wire `src/speakloop/linecards/__init__.py` public API (`LineCard`, `derive_cards`, `select_due`, `advance_card`, `to_anki`, `cloze_from_correction`, `load_starter_cards`, `merge_cards`) — no engine import; mypy-clean.
- [X] T020 [US1] Write `src/speakloop/linecards/CLAUDE.md` (purpose, public interface, deps [feedback.frontmatter, srs.schedule, store], consumers [cli/deck], file map, traps — rebuildable content / live scheduling).

### Config (US1)

- [X] T021 [US1] Add optional `deck_daily_capacity` (default 20, floor 1) to `LoopConfig` + `load()` (via `_int`) in `src/speakloop/config/loop_config.py`; document the key in `src/speakloop/config/CLAUDE.md` loop.yaml table. Add a case to `tests/unit/config/test_loop_config.py` (default + clamp).

### CLI (US1)

- [X] T022 [US1] Implement `src/speakloop/cli/deck.py` `run(*, limit, export_path, ahead, tts_engine, play_fn, key_reader, reports_dir, store_path, starter_cards, today, input_fn, console)` per contracts/deck-command.md: export path (derive+merge → `to_anki` → atomic write → exit); drill path (merge derived+starter+stored state → `select_due` → provision Phase A only when building real TTS → hear/say/see/self-mark → `advance_card` → persist store). All engine imports function-local; non-interactive skips the loop; no report, no recording.
- [X] T023 [US1] Register the `deck` command in `src/speakloop/cli/main.py` (`@app.command("deck")` with `--limit`/`--export`/`--ahead`, function-local import of `cli.deck`).
- [X] T024 [US1] Add `tests/unit/cli/test_deck_command.py` (mirror `test_pronounce_command.py`): inject fake TTS/play/key_reader/store + report fixtures; assert hear-before-see order, self-mark reschedules + persists, `--export` writes a `{{c1::` file and does not drill, non-interactive skips cleanly, and NO `.md` report is written.
- [X] T025 [US1] Document the `deck` command in `src/speakloop/cli/CLAUDE.md` (public interface + file-map entry for `deck.py`).

**Checkpoint (US1 done / MVP)**: `uv run pytest tests/unit/linecards tests/unit/store tests/unit/cli/test_deck_command.py -q` green; `uv run speakloop deck --help` loads no engine; `uv run mypy` green.

---

## Phase 4: User Story 2 — Answer shadowing (`speakloop shadow`) — Priority P2

**Goal**: A learner shadows a question's ideal answer sentence-by-sentence — hear → repeat → deterministic content-word completeness + pace/fillers — fully offline, ephemeral, no report.

**Independent test**: With a multi-sentence ideal answer, `speakloop shadow` speaks each sentence, transcribes the repeat (injected fake in tests), and reports covered/missed key words + pace/fillers; a dotted token doesn't split a sentence; empty repeat → "not captured"; no report, no residual wav.

### `shadowing/` pure logic (US2)

- [X] T026 [P] [US2] Implement `split_sentences(text) -> list[str]` (paragraph split on blank lines; guarded `[.?!]` splitter that does NOT break on digit.digit, dotted/`camelCase` identifiers, or a small abbreviation set; merge sub-floor fragments) in `src/speakloop/shadowing/split.py`.
- [X] T027 [P] [US2] Add `tests/unit/shadowing/test_split.py`: real `ideal_answer` fixtures split into the expected sentences; `"API 28"`, a decimal, and a dotted identifier are NOT split; paragraph breaks are boundaries; single-sentence answer → one item.
- [X] T028 [P] [US2] Implement `judge_completeness(sentence, repeat_text) -> CompletenessResult` (content words = normalized tokens minus stopword set; covered/missed by normalized containment; `coverage`; `captured=False` on empty repeat) in `src/speakloop/shadowing/judge.py` (reuse `warmup`-style normalization).
- [X] T029 [P] [US2] Add `tests/unit/shadowing/test_judge.py`: covered/missed lists correct; function words excluded; `coverage` fraction; deterministic for a fixed transcript; empty transcript → `captured=False` (not a coverage failure).
- [X] T030 [US2] Wire `src/speakloop/shadowing/__init__.py` public API (`split_sentences`, `judge_completeness`, `CompletenessResult`) — no engine import; mypy-clean.
- [X] T031 [US2] Write `src/speakloop/shadowing/CLAUDE.md` (purpose, public interface, deps, consumers [cli/shadow], file map, determinism/offline traps).

### CLI (US2)

- [X] T032 [US2] Implement `src/speakloop/cli/shadow.py` `run(*, question_id, limit, slow, tts_engine, play_fn, record_fn, transcribe_fn, key_reader, qa_file, scratch_dir, input_fn, console)` per contracts/shadow-command.md: resolve+load Q&A, pick question, `split_sentences`, provision Phase B only when building real engines (NOT `ensure_pronunciation_model`/`build_scorer`), per-sentence hear (reuse `pronounce`'s `speak`/`teach_speak` closures + `--slow`) → record (`coordinator._record_stage`) → `transcribe_fn(wav)` → delete wav → `judge_completeness` + `metrics.compute_all`. Function-local engine imports; non-interactive skips; no report, no store write.
- [X] T033 [US2] Register the `shadow` command in `src/speakloop/cli/main.py` (`@app.command("shadow")` with `--question`/`--limit`/`--slow`, function-local import of `cli.shadow`).
- [X] T034 [US2] Add `tests/unit/cli/test_shadow_command.py` (mirror `test_pronounce_command.py`): inject fake TTS/play/record/`transcribe_fn`/key_reader + a Q&A fixture; assert speak-before-feedback per sentence, covered/missed reported, empty transcript → not-captured, scratch wav deleted, NO `.md` report written; determinism for a fixed injected transcript.
- [X] T035 [US2] Document the `shadow` command in `src/speakloop/cli/CLAUDE.md` (public interface + file-map entry for `shadow.py`).

**Checkpoint (US2 done)**: `uv run pytest tests/unit/shadowing tests/unit/cli/test_shadow_command.py -q` green; `uv run speakloop shadow --help` loads no engine; `uv run mypy` green.

---

## Phase 5: Polish & Cross-Cutting

- [X] T036 Extend `tests/integration/test_help_without_models.py` and/or `tests/unit/asr/test_engine_import_isolation.py` to assert importing `speakloop.cli.deck` and `speakloop.cli.shadow` (and the whole CLI) loads no engine package (`kokoro_mlx`, `mlx_whisper`, `parakeet_mlx`, `torch`, `transformers`, …).
- [X] T037 Update the root `CLAUDE.md` module table + Commands section + Pointers: add `deck`/`shadow` to the `cli/` row and Commands block; add `linecards`/`shadowing` module rows; add a `specs/018` pointer. Re-check the 200-line budget (`tests/integration/test_context_file_budget.py`).
- [X] T038 [P] Append a one-paragraph pointer in `doc/research_methodology.md` linking §2.2 (shadowing) and §3.4 (productive-cloze) to feature 018 (non-gating; keeps Principle X current).
- [X] T039 Run the full gates and fix any regression: `uv run pytest` (expect ≥ 926 + new tests, all green), `uv run mypy` (green), `uv run ruff check src/speakloop/linecards src/speakloop/shadowing src/speakloop/cli/deck.py src/speakloop/cli/shadow.py` (no new findings; add a `cli/deck.py`/`cli/shadow.py` `B904` per-file-ignore in `pyproject.toml` only if typer `Exit` re-raises require it).
- [X] T040 Verify the byte-identical / additive invariants hold: a store without `line_cards` loads unchanged; no report is written by either command (grep the run output dir in the CLI tests); `schema_version`/`STORE_VERSION` unchanged.

---

## Dependencies & completion order

- **Setup (T001–T003)** → everything.
- **Foundational (T004–T006)** → US1 scheduling (T017). US2 does not depend on it.
- **US1 (T007–T025)**: store (T007–T010) and `linecards` pure logic (T011–T020) are mostly parallel; `deck.py` selection (T017) needs `advance` (T004) + `cards` (T011); `cli/deck.py` (T022) needs the `linecards` API (T019) + store (T007); tests follow their sources.
- **US2 (T026–T035)**: `split`/`judge` (T026–T029) are parallel; `cli/shadow.py` (T032) needs the `shadowing` API (T030); tests follow their sources. **US2 is fully independent of US1.**
- **Polish (T036–T040)** → after both stories (T037/T039/T040 touch shared files/gates).

**Shared-file serialization**: `cli/main.py` (T023, T033), `cli/CLAUDE.md` (T025, T035), and `pyproject.toml` (T001, T039) are each touched by more than one task → those tasks are NOT run in parallel with each other.

## Parallel execution examples

- **US1 pure logic in parallel**: T011 (`cards.py`), T013 (`cloze.py`), T015 (`starter.py`) + their tests T012/T014/T016 — all different files.
- **US2 pure logic in parallel**: T026 (`split.py`) + T028 (`judge.py`) + tests T027/T029.
- **Cross-story parallel**: once Setup is done, the entire US2 track (T026–T035) can proceed alongside US1 since they share no source files except `cli/main.py`/`cli/CLAUDE.md` (serialize only those two).

## Implementation strategy

1. **MVP = US1 (`deck`)**: Setup → Foundational → Phase 3. Ship the self-graded rescue-lines deck + Anki export alone; it is independently valuable and testable.
2. **Increment = US2 (`shadow`)**: Phase 4, independent of US1.
3. **Polish**: Phase 5 gates + context-file + invariant checks before the final commit.
