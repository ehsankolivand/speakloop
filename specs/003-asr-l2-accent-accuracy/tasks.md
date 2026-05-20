---
description: "Task list for ASR Accuracy on Persian-L1 Accented Technical English"
---

# Tasks: ASR Accuracy on Persian-L1 Accented Technical English

**Input**: Design documents from `specs/003-asr-l2-accent-accuracy/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Compass**: `doc/research_asr_l2_accent.md` (Constitution Principle X)

**Tests**: INCLUDED — the spec mandates them (FR-010 reproducibility gate, SC-C
pause tests, hand-transcribed fixtures). Live model calls remain forbidden
(Development Guidelines): Whisper / Silero / Parakeet are stubbed in unit and
integration tests; only the `@pytest.mark.repro` gate touches real audio and it
skips cleanly when recordings are absent.

**Organization**: by user story (US1 P1 → US2 P2 → US3 P3). Each story leaves a
complete working system; Parakeet stays a working engine throughout.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no incomplete-task dependency)
- **[Story]**: US1 / US2 / US3 (omitted for Setup, Foundational, Polish)

## Path Conventions

Single-project Python CLI: code under `src/speakloop/`, tests under `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependencies, test marker, and the model manifest entry.

- [X] T001 [P] Add pinned deps `mlx-whisper`, `silero-vad`, `onnxruntime` to `[project.dependencies]` in `pyproject.toml` (pin exact versions per research §E.1 / §S5 to guard `mlx-whisper` API drift), then run `uv sync`
- [X] T002 [P] Register the `repro` pytest marker under `[tool.pytest.ini_options]` `markers` in `pyproject.toml` (so `-m repro` and `-m "not repro"` select the local-only acceptance gate)
- [X] T003 Add `WHISPER_LARGE_V3_TURBO = Model(hf_repo_id="mlx-community/whisper-large-v3-turbo", expected_size_bytes=1_613_979_758)` to `src/speakloop/installer/manifest.py` and include it in `PHASE_B_MODELS` and `PHASE_C_MODELS` (keep `PARAKEET_TDT_06B_V3` for the fallback)

**Checkpoint**: deps installed, model downloadable via the existing resumable installer, `repro` marker known to pytest.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the additive Protocol surface every engine implements. **No user story can begin until this is complete.**

- [X] T004 Extend the ASR contract in `src/speakloop/asr/interface.py` per `contracts/asr-interface.py`: add the frozen `TranscriptionContext` dataclass (`initial_prompt`, `initial_prompt_sha256`, `use_vad=True`), add the optional `context: TranscriptionContext | None = None` keyword to `ASREngine.transcribe`, and add `ensure_loaded() -> None` to the Protocol. `Transcript` / `WordTiming` / `ASREngineError` stay unchanged.
- [X] T005 Update `src/speakloop/asr/parakeet_engine.py` to satisfy the extended Protocol: accept-and-ignore the `context` kwarg on `transcribe` (no behaviour change), and add `ensure_loaded()` delegating to the existing `_load()` (idempotent). (depends on T004)
- [X] T006 Re-export `TranscriptionContext` from `src/speakloop/asr/__init__.py` (alongside the existing `ASREngine`/`Transcript`/`WordTiming`/`ASREngineError`). (depends on T004)
- [X] T007 [P] Update `tests/contract/test_asr_interface.py` to assert the extended contract: `transcribe` accepts `context=` and works with `context=None`, `ensure_loaded` exists, `Transcript` shape unchanged. (depends on T004)
- [X] T008 [P] Update `tests/unit/asr/test_parakeet_engine.py`: passing a `TranscriptionContext` does not change Parakeet output, and `ensure_loaded()` is idempotent (stub `_load`). (depends on T005)

**Checkpoint**: both engines conform to the additive Protocol; existing callers (passing no `context`) are unaffected.

---

## Phase 3: User Story 1 - Faithful technical transcript (Priority: P1) 🎯 MVP

**Goal**: Swap the default engine to Whisper-large-v3-turbo with per-session domain biasing, and record provenance — so technical jargon transcribes correctly and the result is reproducible. (Engine selection/flag and VAD come in US3/US2; this story alone fixes the core mishearing.)

**Independent Test**: run a Phase-C session on the default engine; the report transcript contains the correct technical tokens and the frontmatter carries the additive `asr:` block; the repro gate runs green on the user's recordings (skips cleanly without them).

### Tests for User Story 1

- [X] T009 [P] [US1] Unit-test domain-context mining in `tests/unit/asr/test_domain_context.py`: the kotlin-coroutines prompt yields a term set containing {Kotlin, coroutine, threads, dispatcher, IO-bound, CPU-bound, mutex, shared pool}; the assembled prompt includes the seed lexicon and the literal Persian-accent declaration; `initial_prompt_sha256` is the sha256 of the exact prompt string; an empty/term-less prompt still yields seed + accent declaration (edge case).
- [X] T010 [P] [US1] Unit-test additive frontmatter round-trip in `tests/unit/feedback/test_frontmatter_asr.py`: `dump(session)` with `session.asr` set emits a top-level `asr:` block with `schema_version: 1`; `parse` restores it; `dump` with `session.asr=None` is byte-identical to a v1 report; an `asr:`-bearing report still parses through `trends/reader.py` unchanged.
- [X] T011 [P] [US1] Create the repro gate: `tests/fixtures/repro_kotlin_coroutines/` (`expected_tokens.yaml` listing the SC-A tokens, `baseline_parakeet.json` known-bad output, `README.md` explaining how to drop in `attempt-*.wav` + `hand_transcript.txt`, and a `.gitignore` so `*.wav` are never committed — FR-010 privacy), and `tests/integration/repro_gate_test.py` marked `@pytest.mark.repro` that runs the pipeline on the recordings, asserts each target token correct in ≥4/5 occurrences (SC-A) and ≥30% relative technical-token WER reduction vs baseline on the hand-labeled token set (SC-B), and **skips with a clear message when no `.wav` are present**.
- [X] T012 [P] [US1] Create the fresh-recording 5/5 test `tests/integration/repro_fresh_5of5_test.py` marked `@pytest.mark.repro` (Clarification Q1): five clean re-recordings of clearly-pronounced target terms each transcribe the term correctly in all 5; skips cleanly without audio.
- [X] T013 [P] [US1] Integration test `tests/integration/asr_whisper_context_test.py`: with `mlx_whisper.transcribe` monkeypatched, assert `WhisperMLXEngine.transcribe(..., context=ctx)` forwards `initial_prompt=ctx.initial_prompt`, `language="en"`, `condition_on_previous_text=False`, `word_timestamps=True`, and returns a populated `Transcript`.

### Implementation for User Story 1

- [X] T014 [P] [US1] Create `src/speakloop/asr/seed_lexicon.py` — a module-level tuple of high-frequency interview/engineering terms (coroutines, threads, mutex, async, await, dispatcher, semaphore, deadlock, race condition, dependency injection, Jetpack Compose, MVI, clean architecture, Kubernetes, Redis, Postgres, REST, gRPC, latency, throughput, idempotent) per research §S/C.1. Pure constant, no I/O.
- [X] T015 [US1] Create `src/speakloop/asr/domain_context.py` — pure helper: mine proper-noun / CamelCase / capitalized-multiword / lexicon-matching terms from `Question.question` (+ `Question.tags`), join with the seed lexicon and the constant accent declaration "The following is technical English spoken with a Persian accent.", and return a `TranscriptionContext` (prompt + sha256). (depends on T014)
- [X] T016 [US1] Create `src/speakloop/asr/whisper_mlx_engine.py` — the ONLY file allowed to `import mlx_whisper` (Principle V). Lazy, memoized model load on `self._model` with `ensure_loaded()` (mirrors `ParakeetEngine._load`); `transcribe(wav_path, *, context=None)` calls `mlx_whisper.transcribe(path, path_or_hf_repo=<turbo>, initial_prompt=context.initial_prompt, condition_on_previous_text=False, language="en", word_timestamps=True)` and maps the result to `Transcript`/`WordTiming`. **No VAD yet** (added in US2). Raise `ASREngineError` on load/transcribe failure.
- [X] T017 [US1] Extend `src/speakloop/feedback/frontmatter.py` per data-model §A.5/§B: add the `AsrProvenance` dataclass and the additive `Session.asr` field; `dump` emits a top-level `asr:` mapping (engine, model, initial_prompt, initial_prompt_sha256, vad, fell_back) **only when `session.asr` is set**; `parse` reads it back when present; `SCHEMA_VERSION` stays `1`.
- [X] T018 [US1] Wire `src/speakloop/sessions/coordinator.py`: at session start build a `TranscriptionContext` from the `Question` via `domain_context`, pass `context=` into every `asr_engine.transcribe(...)` call, and populate `session.asr` (engine/model/prompt/sha256; `vad`/`fell_back` filled by US2/US3) before the report is dumped. (depends on T015, T016, T017)
- [X] T019 [US1] In `src/speakloop/cli/practice.py`, make Whisper the default: construct `WhisperMLXEngine` once before the practice loop, call `ensure_loaded()` once (cold load outside the timed attempt — research §c), and inject it into every `run_session` (replacing the direct `ParakeetEngine()` default). The `import mlx_whisper` MUST stay **function-local inside `whisper_mlx_engine.py`** (the existing `ParakeetEngine._load` pattern), and `practice.py` MUST import `WhisperMLXEngine` lazily (function-local), so `speakloop --help` remains model-free (Constitution Principle VIII; guarded by T041). (depends on T016)

**Checkpoint**: default sessions transcribe jargon correctly; `asr:` provenance recorded; `uv run pytest -m repro` is green on the user's audio (or skips). MVP shippable.

---

## Phase 4: User Story 2 - Pause-tolerant transcription (Priority: P2)

**Goal**: Silero-VAD pre-segmentation so 2–5 s thinking pauses never produce phantom tokens, while preserving the pause timeline so fluency metrics stay correct.

**Independent Test**: attempts with deliberate silent pauses produce zero tokens in the silence windows (SC-C), and the pauses still appear in `pauses_count`/`mean_pause_ms`.

### Tests for User Story 2

- [X] T020 [P] [US2] Unit-test `tests/unit/asr/test_vad.py` (stub the silero speech-probability output): regions shorter than `MIN_SPEECH_MS` dropped, regions separated by ≤`MERGE_GAP_MS` merged, `SPEECH_PAD_MS` padding applied and clamped, all-silence input → `[]`, regions sorted/non-overlapping on the original timeline.
- [X] T021 [P] [US2] Integration test `tests/integration/asr_pipeline_test.py`: with VAD returning two regions around a gap and `mlx_whisper.transcribe` stubbed per region, assert word timings are offset onto the original timeline (pause gap preserved → pause metric non-zero) and that audio from the silent region is never passed to the ASR; all-silence input yields an empty `Transcript`.
- [X] T022 [P] [US2] Integration test `tests/integration/test_pause_tolerance.py` (SC-C): build/load silence-padded fixtures under `tests/fixtures/silence_clips/` (2–5 s pauses); with a stub Whisper that *would* emit a token on silence, assert VAD removes the silent region so zero tokens land in the silence windows across the fixture set.

### Implementation for User Story 2

- [X] T023 [US2] Create `src/speakloop/asr/vad.py` per `contracts/vad-contract.py` — the ONLY file allowed to `import silero_vad`/`onnxruntime` (Principle V): named tunables (`SPEECH_THRESHOLD=0.5`, `MIN_SPEECH_MS=250`, `MIN_SILENCE_MS=100`, `MERGE_GAP_MS=300`, `SPEECH_PAD_MS=30`, `SAMPLE_RATE_HZ=16000`), `segment(wav_path) -> list[SpeechRegion]` (16 kHz mono, drop/merge/pad, original timeline), and `vad_settings() -> dict` for provenance. No SNR/denoise (out of scope — research §b).
- [X] T024 [US2] Integrate VAD into `src/speakloop/asr/whisper_mlx_engine.py`: when `context.use_vad` (default True), run `vad.segment`, transcribe each speech region, offset each region's word timings by its `start_seconds`, and reassemble one `Transcript` preserving inter-region gaps; all-silence → empty `Transcript`. `context.use_vad=False` keeps the whole-clip path. (depends on T023, T016)
- [X] T025 [US2] Populate the `vad` block of `session.asr` provenance (the tunables that ran, or `null` when disabled) in `src/speakloop/sessions/coordinator.py` / `frontmatter.py`. (depends on T024, T017)

**Checkpoint**: US1 + US2 work; pauses tolerated, metrics intact, VAD settings recorded.

---

## Phase 5: User Story 3 - Engine selection & graceful fallback (Priority: P3)

**Goal**: `--asr-engine` flag for power users; automatic fallback to Parakeet with one visible line if Whisper cannot load; provenance records the engine actually used.

**Independent Test**: force a Whisper load failure → session completes on Parakeet with one English notice and `asr.fell_back: true`; `--asr-engine parakeet` runs Parakeet with no notice.

### Tests for User Story 3

- [X] T026 [P] [US3] Unit-test `tests/unit/asr/test_selection.py` (stub both engine classes): `build_engine()` default returns Whisper; when Whisper `ensure_loaded` raises, returns Parakeet with `fell_back=True` and an English `fallback_reason`; `build_engine("parakeet")` returns Parakeet with `fell_back=False`; `EngineSelection` carries the resolved `engine_name`/`model_id`.
- [X] T027 [P] [US3] Integration test `tests/integration/asr_fallback_test.py`: with Whisper `ensure_loaded` raising, a full `run_session` completes on Parakeet, exactly one English fallback line is emitted, and `session.asr` records `engine: parakeet`, `fell_back: true` (SC-F).

### Implementation for User Story 3

- [X] T028 [US3] Create `src/speakloop/asr/selection.py` per `contracts/asr-interface.py`: `build_engine(name) -> EngineSelection` constructs the requested engine (default Whisper), eagerly calls `ensure_loaded()` to detect load failure before attempt 1, falls back to Parakeet on failure (set `fell_back`, English `fallback_reason`), honors an explicit `parakeet` with no fallback, and carries `engine_name`/`model_id`. Imports the two wrapper classes only — no third-party engine import (Principle V). (depends on T004, T005, T016)
- [X] T029 [US3] Re-export `build_engine` and `EngineSelection` from `src/speakloop/asr/__init__.py`. (depends on T028)
- [X] T030 [US3] In `src/speakloop/cli/practice.py`, add the `--asr-engine {whisper,parakeet}` option (default whisper), resolve via `asr.build_engine`, print one English line when `selection.fell_back`, and inject `selection.engine` into the loop (reusing the construct-once pattern). The `import mlx_whisper` MUST remain **function-local inside `whisper_mlx_engine.py`**, and `selection.py` / `practice.py` MUST import the engine wrappers lazily, so `speakloop --help` stays model-free (Constitution Principle VIII; guarded by T041). (depends on T028, T019)
- [X] T031 [US3] Thread the resolved `engine_name`/`model_id`/`fell_back` from the selection into `session.asr` so provenance reflects the engine that actually ran, via `src/speakloop/sessions/coordinator.py`. (depends on T028, T017)

**Checkpoint**: all three stories independently functional; 100% of sessions complete (SC-F); flag and provenance work.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T032 [P] Update `src/speakloop/asr/CLAUDE.md`: new default engine, `--asr-engine` flag, VAD, domain context, selection/fallback, and the `mlx_whisper`/`silero_vad`/`onnxruntime` isolation files (Principle IV/V).
- [X] T033 [P] Update `src/speakloop/cli/CLAUDE.md`: document `--asr-engine` and the Whisper default.
- [X] T034 [P] Update `src/speakloop/feedback/CLAUDE.md`: note the additive `Session.asr` provenance field (schema_version stays 1).
- [X] T035 [P] Update `doc/research_asr.md`: add a pointer to `doc/research_asr_l2_accent.md` and record the default-engine swap to Whisper (Principle X — changing an engine requires updating the research doc).
- [X] T036 [P] Update the top-level `CLAUDE.md` module map note for `asr/`: default engine now Whisper-large-v3-turbo, Parakeet as flag + fallback.
- [X] T039 [P] Add an engine-import isolation test (Principle V / FR-011) in `tests/unit/asr/test_engine_import_isolation.py`: statically scan `src/speakloop/` (AST or source-grep) and assert `mlx_whisper` is imported only in `asr/whisper_mlx_engine.py`, and `silero_vad`/`onnxruntime` only in `asr/vad.py`. Generalizes the Principle V guard the v1 "T109" task intended (which only covered `parakeet_mlx`); fold in `parakeet_mlx` → `asr/parakeet_engine.py` while here so all engine deps are guarded. (depends on T016, T023)
- [X] T040 Add a warm-model / load-once test (guards SC-D, research §c) in `tests/integration/asr_model_memoization_test.py`: with a stubbed loader exposing a call counter, run 3 attempts + 1 replay through the practice/coordinator path and assert `ensure_loaded`/`_load` is invoked exactly once (no per-attempt or per-replay reload). (depends on T016, T019, T024)
- [X] T041 [P] Add a model-free CLI test (Constitution Principle VIII) in `tests/integration/test_help_without_models.py`: assert `speakloop --help` exits 0 and prints usage with no models present (no model dirs, engine packages not imported at module load), proving the Whisper/VAD imports stay function-local. (depends on T019)
- [X] T037 Run `uv run ruff check src tests` and `uv run pytest -m "not repro"` (full model-free suite, including T039–T041) green. Run after T039–T041 land.
- [X] T038 Run `specs/003-asr-l2-accent-accuracy/quickstart.md` end-to-end locally, including `uv run pytest -m repro` against the user's own recordings (SC-A/SC-B/SC-C, SC-D latency, SC-F fallback).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories** (the Protocol surface).
- **User Stories (Phase 3–5)**: all depend on Foundational. US1 is the MVP. US2 builds on the US1 Whisper engine (modifies `whisper_mlx_engine.py`). US3 depends on the US1 engine + US1 CLI wiring. US2 and US3 are otherwise independent of each other and can proceed in parallel after US1.
- **Polish (Phase 6)**: after the desired stories are complete.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on other stories. Independently shippable.
- **US2 (P2)**: after US1 (extends the Whisper engine + provenance). Independently testable via pause fixtures.
- **US3 (P3)**: after US1 (needs the Whisper engine + the construct-once CLI wiring). Independently testable via forced load failure. Independent of US2.

### Within Each Story

- Tests are written to fail first, then implementation.
- `seed_lexicon` → `domain_context`; engine + frontmatter before coordinator wiring; coordinator before CLI default.

### Parallel Opportunities

- Setup: T001, T002 in parallel (T003 touches manifest independently).
- Foundational: T007, T008 in parallel after T004/T005.
- US1 tests T009–T013 all [P]; impl T014 [P] then T015/T016/T017 (T016 and T017 are different files → parallelizable) before T018/T019.
- US2 tests T020–T022 all [P].
- US3 tests T026, T027 [P].
- Polish T032–T036 all [P] (different docs); T039 and T041 [P] (different test files); T040 depends on the engine + CLI wiring. T037 (suite) and T038 (quickstart) run last, after T039–T041.

---

## Parallel Example: User Story 1

```bash
# Tests for US1 (all different files) — write first, expect failure:
Task: "Unit test domain_context in tests/unit/asr/test_domain_context.py"
Task: "Unit test frontmatter asr round-trip in tests/unit/feedback/test_frontmatter_asr.py"
Task: "Repro gate scaffolding + tests/integration/repro_gate_test.py"
Task: "Fresh 5/5 test in tests/integration/repro_fresh_5of5_test.py"
Task: "Whisper context-forwarding test in tests/integration/asr_whisper_context_test.py"

# Then independent implementation files:
Task: "Create src/speakloop/asr/seed_lexicon.py"
Task: "Create src/speakloop/asr/whisper_mlx_engine.py"
Task: "Extend src/speakloop/feedback/frontmatter.py (AsrProvenance + Session.asr)"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE**:
   run a real Phase-C session and `uv run pytest -m repro` on the user's audio.
   This alone fixes the mishearing and is shippable; Parakeet remains available.

### Incremental Delivery

1. Setup + Foundational → Protocol ready.
2. US1 → faithful transcript + provenance (MVP, SC-A/SC-B).
3. US2 → pause tolerance (SC-C) without breaking US1.
4. US3 → engine flag + fallback (SC-F) without breaking US1/US2.
5. Polish → docs (Principle IV/X), lint, full suite, quickstart + local repro gate.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- Engine-specific imports stay confined to `whisper_mlx_engine.py` (mlx_whisper),
  `vad.py` (silero_vad/onnxruntime), `parakeet_engine.py` (parakeet_mlx);
  `selection.py` composes wrappers only (Principle V).
- `schema_version` stays **1**; the `asr:` key is additive (FR-008; verified safe
  against `trends/reader.py`/`aggregator.py`).
- The user's voice recordings are never committed (FR-010 privacy); the repro
  gate is a manual local gate that skips in CI.
- No live model calls in tests except the `-m repro` gate on local audio.
- Commit after each task or logical group (Conventional Commits).
