# Tasks: speakloop v1 — local English interview-practice CLI

**Input**: Design documents from `/specs/001-v1-product-spec/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: REQUIRED. Per Constitution Development Guidelines and `research.md` § "Testing": `pytest` with **committed fixtures** under `tests/fixtures/`, **no live model calls**. Every TTS/ASR/LLM engine wrapper gets a unit test that uses cached fixture WAVs / transcripts; every contract surface under `contracts/` gets a contract test.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. Story IDs map to spec.md priorities (US1..US6). Phases A/B/C from plan.md § "Phase shipping order" are noted on tasks that materially differ across phases.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5, US6)
- Include exact file paths in descriptions

## Path Conventions

Single-project Python CLI per plan.md § "Project Structure":

- Source: `src/speakloop/<module>/`
- Tests: `tests/unit/<module>/`, `tests/contract/`, `tests/integration/`
- Fixtures: `tests/fixtures/{wav,transcripts,qa}/` (committed)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure per plan.md.

- [X] T001 Create directory tree under `src/speakloop/` for the twelve first-level modules (`config`, `cli`, `installer`, `content`, `tts`, `audio`, `asr`, `metrics`, `llm`, `feedback`, `sessions`, `trends`), each with empty `__init__.py`; create `tests/{unit,contract,integration,fixtures}/`; create `data/sessions/.gitkeep`
- [X] T002 Initialize `uv`-managed Python 3.12 project: `pyproject.toml` with `name = "speakloop"`, `requires-python = ">=3.12,<3.13"` (3.13 conflicts per plan.md), MIT license, entrypoint `speakloop = "speakloop.cli.main:app"`, dependencies stub (`typer`, `rich`, `pyyaml`, `sounddevice`, `soundfile`, `huggingface_hub`, `python-frontmatter`); run `uv sync` to materialise `.venv`
- [X] T003 [P] Add `LICENSE` (MIT) at repository root per Constitution Non-Negotiable Constraints
- [X] T004 [P] Add `.gitignore` at repository root (`.venv/`, `__pycache__/`, `*.egg-info/`, `data/sessions/*.md`, `data/sessions/*.tmp`, `.DS_Store`)
- [X] T005 [P] Configure `ruff` (lint + format) in `pyproject.toml` `[tool.ruff]` block — target-version py312
- [X] T006 [P] Configure `pytest` in `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, markers for `unit`, `contract`, `integration`, `slow`
- [X] T007 [P] Author top-level `CLAUDE.md` mapping all twelve first-level modules to their `CLAUDE.md` files, per Constitution Principle XI
- [X] T008 [P] Scaffold per-module `CLAUDE.md` files under each of `src/speakloop/{config,cli,installer,content,tts,audio,asr,metrics,llm,feedback,sessions,trends}/CLAUDE.md` — single-responsibility statement + public surface (Principle IV)
- [X] T009 [P] Author `README.md` at repository root linking to `specs/001-v1-product-spec/quickstart.md` and `.specify/memory/constitution.md`
- [X] T010 Create fixture sub-directory tree `tests/fixtures/{wav/tts,wav/recordings,transcripts,qa}/` with `.gitkeep` placeholders so subsequent fixture-commit tasks have a target

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core contracts + fixtures + CLI skeleton that all user stories depend on. Until this is complete, no user story phase can begin.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T011 [P] Implement `src/speakloop/config/paths.py` — `models_dir()`, `sessions_dir()`, `qa_file_path()`, `tts_cache_dir()` with `~/.speakloop/` defaults and XDG-compliant overrides (data-model.md § Storage; Constitution Non-Negotiable)
- [X] T012 [P] Define `TTSEngine` Protocol + `TTSEngineError` in `src/speakloop/tts/interface.py` — verbatim shape from `contracts/tts-interface.py` (STABLE — Principle V)
- [X] T013 [P] Define `ASREngine` Protocol + `Transcript` + `WordTiming` + `ASREngineError` in `src/speakloop/asr/interface.py` — verbatim shape from `contracts/asr-interface.py` (STABLE — Principle V)
- [X] T014 [P] Define `LLMEngine` Protocol + `LLMEngineError` in `src/speakloop/llm/interface.py` — verbatim shape from `contracts/llm-interface.py` (STABLE — Principle V)
- [X] T015 Implement `src/speakloop/cli/main.py` — `typer` app skeleton with `--help`, `--version`, `--qa-file`, `--models-dir` global options, and subcommand stubs for `practice`, `doctor`, `trends`; MUST NOT import any engine module at module load (FR-018, SC-006 ≤ 2 s)
- [X] T016 Implement `tests/conftest.py` — `pytest` fixture loaders for `wav_fixture(name)`, `transcript_fixture(name)`, `qa_fixture(name)`; `tmp_models_dir` + `tmp_sessions_dir` fixtures pointing at `tmp_path`
- [X] T017 [P] Commit pre-synthesized fixture WAVs under `tests/fixtures/wav/tts/` — `question-short.wav` (≤ 3 s), `ideal-answer-short.wav` (≤ 5 s); generated out-of-band, committed binary (Constitution Dev Guidelines)
- [X] T018 [P] Commit pre-recorded attempt fixture WAVs under `tests/fixtures/wav/recordings/` — `attempt-short.wav` (≤ 10 s with speech), `attempt-silent.wav` (≤ 5 s silence for FR-009 / silent-attempt edge case)
- [X] T019 [P] Commit fixture transcripts under `tests/fixtures/transcripts/` — `attempt-short.txt`, `attempt-silent.txt` (empty file), and a multi-attempt fixture set `session-3attempts/{attempt1.txt,attempt2.txt,attempt3.txt}` exercising fillers, repeats, repair markers, and seed-5 grammar patterns
- [X] T020 [P] Commit Q&A YAML fixtures under `tests/fixtures/qa/` — `valid.yaml` (2 questions matching `contracts/content-schema.yaml`), `invalid-syntax.yaml` (deliberate YAML syntax error at a known line), `missing-field.yaml` (entry missing required `ideal_answer`)
- [X] T021 [P] [contract] Implement `tests/contract/test_tts_interface.py` — define a `StubTTSEngine` returning a fixture WAV path; assert it satisfies `TTSEngine` protocol structurally; assert `TTSEngineError` inherits `Exception`
- [X] T022 [P] [contract] Implement `tests/contract/test_asr_interface.py` — assert `Transcript(text="", words=[], audio_duration_seconds=0.0).is_empty is True`; define a `StubASREngine` returning a fixture `Transcript`; assert it satisfies `ASREngine` protocol structurally
- [X] T023 [P] [contract] Implement `tests/contract/test_llm_interface.py` — define a `StubLLMEngine` returning a canned string; assert it satisfies `LLMEngine` protocol structurally; assert the stub's output contains no `<think>` substring (Qwen3-8B leak guard documented in contract)
- [X] T024 [P] [contract] Implement `tests/contract/test_cli_commands.py` — invoke `speakloop --help` via `typer.testing.CliRunner` and assert exit 0, output mentions `practice`, `doctor`, `trends` (FR-018); invoke `speakloop --version` and assert exit 0; verify global options `--qa-file` and `--models-dir` are documented in `--help`
- [X] T025 [P] [contract] Implement `tests/contract/test_content_schema.py` — `yaml.safe_load` of `contracts/content-schema.yaml` example; assert `schema_version == 1` and each question has required fields per data-model.md §1
- [X] T026 [P] [contract] Implement `tests/contract/test_report_frontmatter.py` — `yaml.safe_load` of `contracts/report-frontmatter.yaml` example; assert required keys (`schema_version`, `session_id`, `started_at`, `question_id`, `question`, `attempts` length 3, `grammar_patterns`, `generated_by_phase`); assert per-attempt metric keys exactly match data-model.md §5

**Checkpoint**: Foundation ready — user-story implementation can now begin in parallel. `speakloop --help` already works model-free (FR-018, SC-006).

---

## Phase 3: User Story 3 — First-run setup with informed consent and resumable downloads (Priority: P1) [Phase A] 🎯 part of MVP

**Goal**: A new user is walked through one-time model setup with size disclosure, explicit consent (decline-by-default), and a `huggingface_hub` resumable download that survives Ctrl+C / network drops.

**Independent Test**: With an empty `models_dir` and `huggingface_hub.snapshot_download` monkeypatched to a controllable fake, the installer flow prints the model list with sizes, asks `Proceed with download? [y/N]:`, exits 1 cleanly on decline (no files written), and on accept downloads + validates + exits 0; interrupting the fake mid-stream and re-running resumes with ≤ 1 % re-fetch of completed bytes (SC-002).

### Tests for User Story 3

- [X] T027 [P] [US3] Unit test `tests/unit/installer/test_manifest.py` — assert `PHASE_A_MODELS` contains TTS only, `PHASE_B_MODELS` adds ASR, `PHASE_C_MODELS` adds LLM (data-model.md §9); each `Model` has `name`, `hf_repo_id`, `expected_size_bytes`, `local_path`, `required_for_phase`
- [X] T028 [P] [US3] Unit test `tests/unit/installer/test_consent.py` — `prompt_for_consent(models)` returns `False` on `n`, on EOF, and on empty input (decline-by-default per `contracts/cli-commands.md` § "First-run flow"); returns `True` only on explicit `y` / `yes`; rich-rendered output includes per-model size and total disk footprint (FR-019)
- [X] T029 [P] [US3] Unit test `tests/unit/installer/test_downloader.py` — monkeypatch `huggingface_hub.snapshot_download` to record call kwargs; assert `resume_download=True` is passed (FR-021); simulate two calls where the second represents a resume from a partial directory and assert the fake observed the existing partial files (proxy for SC-002 ≤ 1 % re-fetch)
- [X] T030 [P] [US3] Unit test `tests/unit/installer/test_validator.py` — write a file matching `expected_size_bytes` → validator returns OK; write a file with wrong size → validator returns FAIL with reason `size_mismatch`; missing file → FAIL with reason `missing`; corrupt model treated identically to missing (FR-022)
- [X] T031 [US3] Integration test `tests/integration/test_phase_a_install_flow.py` — empty `tmp_models_dir` + fake `snapshot_download` writing fixture-sized files + simulated stdin `"y\n"` → installer exits 0, all manifest entries validated; with stdin `"n\n"` → exits 1 and `tmp_models_dir` is empty (FR-020)

### Implementation for User Story 3

- [X] T032 [P] [US3] Implement `src/speakloop/installer/manifest.py` — `Model` dataclass + `PHASE_A_MODELS` (Kokoro-82M), `PHASE_B_MODELS` (Kokoro + Parakeet-TDT-0.6b-v3), `PHASE_C_MODELS` (+ Qwen3.5-9B-MLX-4bit). `hf_repo_id` and approximate `expected_size_bytes` per `doc/research_{tts,asr,llm}.md`. The ONLY file that needs editing on engine swap at manifest level (Principle V)
- [X] T033 [P] [US3] Implement `src/speakloop/installer/consent.py` — `rich`-rendered prompt listing models with size + target path + total disk footprint; default `N`; FR-019, FR-020
- [X] T034 [US3] Implement `src/speakloop/installer/downloader.py` — `download_model(model: Model) -> None` wrapping `huggingface_hub.snapshot_download(..., resume_download=True, local_dir=model.local_path)` with `rich.progress` overlay; FR-021; depends on T032
- [X] T035 [US3] Implement `src/speakloop/installer/validator.py` — `validate(model: Model) -> ValidationResult`; size check + `etag` marker check per research.md § "Resumable download primitive"; corrupt → missing per FR-022; depends on T032
- [X] T036 [US3] Implement `src/speakloop/installer/__init__.py` — `ensure_models(phase: Literal["A","B","C"]) -> None` orchestrator: compute missing/invalid → consent → download → re-validate → raise on user decline; wire into `cli/main.py` so `practice` and `trends` call it before doing any engine work (`contracts/cli-commands.md` § "First-run flow"); depends on T032–T035

**Checkpoint**: User Story 3 is fully functional and testable independently. A user with an empty `models_dir` can run the installer flow end-to-end against the fake downloader.

---

## Phase 4: User Story 1 — Listen to a question and an ideal answer (Priority: P1) [Phase A] 🎯 MVP

**Goal**: User opens speakloop, picks a question from their Q&A YAML, hears the question and the ideal answer in a native English accent, can replay either as many times as they want, and exits without writing any session artifact.

**Independent Test**: Freshly cloned repo + starter Q&A copied to `~/.speakloop/qa.yaml` + TTS model present (or stub engine). Run `speakloop practice --listen-only`, pick a question, hear question audio, hear ideal-answer audio, replay both, quit. No file appears under `data/sessions/`. Cache directory contains exactly one WAV per `(voice, text)` pair invoked.

### Tests for User Story 1

- [X] T037 [P] [US1] Unit test `tests/unit/content/test_loader.py` — `load(qa_fixture("valid.yaml"))` returns 2 `Question`s; `load(qa_fixture("invalid-syntax.yaml"))` raises with file path + line number message (FR-029); `load(qa_fixture("missing-field.yaml"))` raises naming the entry id and the missing field `ideal_answer` (FR-030)
- [X] T038 [P] [US1] Unit test `tests/unit/content/test_schema.py` — `Question` validation: duplicate `id` across the file → rejected; `id` > 40 chars → rejected; empty `question` after `strip()` → rejected (data-model.md §1); unknown keys → surfaced as warnings, not errors
- [X] T039 [P] [US1] Unit test `tests/unit/tts/test_cache.py` — `cache_key(voice, text)` is `sha256(f"{voice}|{text}")`; `store(key, wav_path)` + `lookup(key)` returns the stored path; lookup miss returns `None`; second call with same `(voice, text)` does NOT touch the engine (FR-004)
- [X] T040 [P] [US1] Unit test `tests/unit/tts/test_kokoro_engine.py` — with `kokoro_mlx` import monkeypatched to a stub that returns a fixture WAV from `tests/fixtures/wav/tts/`, assert `synthesize("hello")` returns a `Path` to a WAV; assert second call with the same text hits the cache and does NOT invoke the stub a second time; raises `TTSEngineError` when the stub raises
- [X] T041 [P] [US1] Unit test `tests/unit/audio/test_playback.py` — with `sounddevice.play` monkeypatched, assert `playback.play(fixture_wav_path)` calls `sd.play` with the WAV's PCM data and `sd.wait()`; no audio actually played in tests
- [X] T042 [US1] Integration test `tests/integration/test_phase_a_listen.py` — `CliRunner.invoke(app, ["practice", "--listen-only", "--question", "kotlin-coroutines-basics"])` with stub TTS engine returning fixture WAVs and `sounddevice.play` mocked → exits 0, plays question then ideal-answer (both calls observed), `data/sessions/` is empty, `~/.speakloop/cache/tts/` has 2 entries (Story 1 AS#1, AS#3)

### Implementation for User Story 1

- [X] T043 [P] [US1] Implement `src/speakloop/content/schema.py` — `Question` + `QAFile` dataclasses with validation per data-model.md §1, §2; matches `contracts/content-schema.yaml`
- [X] T044 [US1] Implement `src/speakloop/content/loader.py` — `yaml.safe_load` (research.md § Q&A format); on `yaml.YAMLError` surface `error.problem_mark.line` and file path (FR-029); on schema error surface entry id + field name (FR-030); depends on T043
- [X] T045 [P] [US1] Author `src/speakloop/content/starter.yaml` — 3–5 questions per spec Assumptions: one system-design, one behavioral, one technical-deep-dive; each conforms to `contracts/content-schema.yaml`
- [X] T046 [P] [US1] Implement `src/speakloop/tts/cache.py` — content-addressed cache at `~/.speakloop/cache/tts/<sha256>.wav` per research.md § "TTS clip cache"; `cache_key`, `lookup`, `store`, `purge`
- [X] T047 [US1] Implement `src/speakloop/tts/kokoro_engine.py` — the ONLY file in the repo that may `import kokoro_mlx` / `import mlx_audio` (Principle V, research.md § TTS); class `KokoroEngine` implements `TTSEngine`; uses `cache.py` so identical `(voice, text)` returns the cached path; raises `TTSEngineError` on any engine failure; depends on T012, T046
- [X] T048 [P] [US1] Implement `src/speakloop/audio/playback.py` — `play(wav_path: Path) -> None` using `sounddevice` + `soundfile` (research.md § "Audio I/O"); blocks until playback finishes; raises a clear error if no output device
- [X] T049 [US1] Implement `src/speakloop/cli/practice.py` (Phase A subset) — load Q&A → picker → listen loop (`q`uit / `r`eplay-question / `R`eplay-answer / `space` continue); honors `--listen-only` and `--question`; uses `tts` + `audio.playback`; FR-001..FR-004; depends on T036, T044, T047, T048
- [X] T050 [US1] On first run, copy `src/speakloop/content/starter.yaml` → `~/.speakloop/qa.yaml` if no user file exists (plan.md § Storage); wire into `cli/main.py` bootstrap path; idempotent on second run

**Checkpoint**: User Story 1 is fully functional and testable independently. With User Story 3 (installer) also complete, the listen-only MVP is end-to-end usable — Phase A ships.

---

## Phase 5: User Story 2 — Complete a full 4/3/2 attempt loop and receive a feedback report (Priority: P1) [Phase B ⇒ Phase C]

**Goal**: After listening, the user records three timed attempts (4/3/2 minutes), the system transcribes each, computes fluency metrics, runs LLM grammar analysis (Phase C), and writes a single Markdown report under `data/sessions/`.

**Independent Test**: Full session with engines mocked to return fixture transcripts → a single Markdown report appears at `data/sessions/YYYY-MM-DD-<question-id>.md` with valid frontmatter + per-attempt metrics + grammar findings (Phase C) or `grammar_patterns: []` + `generated_by_phase: B` (Phase B interim). Ctrl+C aborts cleanly with zero report files on disk.

This story is split across **Phase B** (attempts + transcription + metrics + interim report) and **Phase C** (LLM-driven grammar feedback). Phase B is **unblocked**; Phase C tasks marked **`[BLOCKED]`** depend on `doc/research_methodology.md` being authored (plan.md § Complexity Tracking).

### Tests for User Story 2 — Phase B

- [X] T051 [P] [US2] Unit test `tests/unit/audio/test_recorder.py` — with `sounddevice.InputStream` monkeypatched to emit silence chunks, assert `recorder.record(out_path, time_budget_seconds=2)` writes a 2-second WAV; assert early-stop signal cuts recording at signal time; assert resulting WAV is mono and readable by `soundfile`
- [X] T052 [P] [US2] Unit test `tests/unit/asr/test_parakeet_engine.py` — with `parakeet_mlx` import monkeypatched to a stub that returns a fixed transcript + word timings, assert `transcribe(fixture_wav)` returns the expected `Transcript`; transcribe `attempt-silent.wav` → `transcript.is_empty is True`; raises `ASREngineError` on stub failure
- [X] T053 [P] [US2] Unit test `tests/unit/metrics/test_speech_rate.py` — `words_total` excludes pure punctuation; `speech_rate_wpm = words_total / (actual_duration_seconds / 60)`; zero-duration input → 0.0 without ZeroDivisionError (data-model.md §5)
- [X] T054 [P] [US2] Unit test `tests/unit/metrics/test_pauses.py` — using fixture word timings, compute `pauses_count` and `mean_pause_ms` with a **250 ms threshold** (FR-012b); gaps below threshold are NOT pauses; threshold MUST be the only knob — verify by parameterising the test
- [X] T055 [P] [US2] Unit test `tests/unit/metrics/test_fillers.py` — canonical 10-token set `{um, uh, ah, er, hmm, like, you know, I mean, basically, actually}` (FR-012a); case-insensitive whole-word match; `likely` does NOT match `like`; multi-word phrases `you know` / `I mean` matched as whole phrases; `filler_density_per_100_words = filler_words_count / words_total * 100`
- [X] T056 [P] [US2] Unit test `tests/unit/metrics/test_self_corrections.py` — verbatim repeats: `"the the"`, `"I I went"` count as 1 each; repair markers `{I mean, sorry, let me rephrase, actually no, what I meant, wait}` (case-insensitive whole-phrase, FR-012c) count as 1 each; LLM is NOT invoked (assert by spying that no LLM dependency is touched)
- [X] T057 [P] [US2] Unit test `tests/unit/feedback/test_frontmatter.py` — emit frontmatter from a `Session` fixture; `yaml.safe_load` the emitted block and assert it matches `contracts/report-frontmatter.yaml` keys exactly (schema_version=1); test both `generated_by_phase: B` (grammar_patterns=[]) and `generated_by_phase: C`; multi-line `question:` round-trips via `|` block scalar
- [X] T058 [P] [US2] Unit test `tests/unit/feedback/test_markdown_writer.py` — `write_atomic(path, content)` writes to `<path>.tmp` then `os.replace`; simulate a crash between write and replace by monkeypatching `os.replace` to raise → assert no file at `path` (only `.tmp` remains) (FR-016, SC-005, research.md § "Atomic Markdown writes")
- [X] T059 [P] [US2] Unit test `tests/unit/sessions/test_timer.py` — `time_budget_for(ordinal)` returns 240 / 180 / 120 for ordinals 1/2/3; `Timer.run(budget, on_tick, on_zero, early_exit_event)` invokes `on_zero` exactly when the budget elapses; `early_exit_event.set()` interrupts before zero
- [X] T060 [P] [US2] Unit test `tests/unit/sessions/test_abort.py` — registering the SIGINT handler removes any `*.tmp` files under `sessions_dir()` on signal; exit code is 130 per `contracts/cli-commands.md`
- [X] T061 [US2] Integration test `tests/integration/test_phase_b_attempt.py` — full coordinator run with stub TTS, stub recorder feeding 3 fixture WAVs, stub ASR returning 3 fixture transcripts, real metrics, real markdown_writer → exactly one `.md` file under `tmp_sessions_dir` with frontmatter `generated_by_phase: B`, `grammar_patterns: []`, all 3 attempts present with metric blocks per data-model.md §5
- [X] T062 [US2] Integration test `tests/integration/test_phase_b_abort.py` — invoke coordinator, trigger SIGINT during attempt 2 → 0 `.md` files in `tmp_sessions_dir`, no `.tmp` left behind, exit code 130 (FR-016, SC-005); separately: SIGINT during report-build after attempts complete → raw transcripts MAY be preserved as labelled `.txt` per spec Edge Case "Ctrl+C during post-attempt LLM processing"
- [X] T063 [P] [US2] Integration test `tests/integration/test_phase_b_no_microphone.py` — `audio.devices.default_input()` returns `None` → coordinator refuses to start attempt phase, prints remediation pointing at `speakloop doctor`, exits 1 (FR-009)
- [X] T064 [P] [US2] Integration test `tests/integration/test_phase_b_silent_attempt.py` — stub ASR returns empty `Transcript` for attempt 2 → report acknowledges the silent attempt without crashing; metrics record `words_total=0`, `speech_rate_wpm=0.0`; report still produced (spec Edge Case)
- [X] T065 [P] [US2] Integration test `tests/integration/test_phase_b_filename_disambiguation.py` — write a report for `2026-05-18` + `kotlin-coroutines-basics`, run another session same day same question → second report filename ends `-2.md`; first file is NOT overwritten (FR-017)

### Implementation for User Story 2 — Phase B

- [X] T066 [P] [US2] Implement `src/speakloop/audio/recorder.py` — `record(out_path, time_budget_seconds, early_exit_event)` using `sounddevice.InputStream` → mono WAV via `soundfile`; respects time budget and the early-exit event
- [X] T067 [P] [US2] Implement `src/speakloop/audio/devices.py` — `default_input()`, `default_output()`, `list_devices()` for doctor enumeration and FR-009 pre-check
- [X] T068 [US2] Implement `src/speakloop/asr/parakeet_engine.py` — the ONLY file in the repo that may `import parakeet_mlx` (Principle V, research.md § ASR); class `ParakeetEngine` implements `ASREngine`; returns `Transcript` with word-level timings (RNN-T/TDT does not hallucinate on silence — research.md § ASR); FR-008; depends on T013
- [X] T069 [P] [US2] Implement `src/speakloop/metrics/speech_rate.py` — `words_total`, `speech_rate_wpm` per data-model.md §5
- [X] T070 [P] [US2] Implement `src/speakloop/metrics/pauses.py` — `pauses_count`, `mean_pause_ms` from `WordTiming` list; **250 ms threshold** as the single named constant (FR-012b)
- [X] T071 [P] [US2] Implement `src/speakloop/metrics/fillers.py` — canonical 10-token set (FR-012a) as a module-level constant; case-insensitive whole-word/-phrase matcher; `filler_words_count` + `filler_density_per_100_words`
- [X] T072 [P] [US2] Implement `src/speakloop/metrics/self_corrections.py` — deterministic transcript-only heuristic (FR-012c): verbatim repeat detection + canonical repair-marker set; MUST NOT import `speakloop.llm`
- [X] T073 [P] [US2] Implement `src/speakloop/feedback/frontmatter.py` — emit YAML frontmatter from `Session` dataclass conforming to `contracts/report-frontmatter.yaml`; `schema_version: 1`; key order stable; supports `generated_by_phase` B vs C
- [X] T074 [US2] Implement `src/speakloop/feedback/markdown_writer.py` — `write_atomic(path, content)` via `tempfile.NamedTemporaryFile(dir=path.parent)` + `os.replace` (research.md § "Atomic Markdown writes"); registers cleanup with `sessions/abort.py`; FR-016; depends on T073
- [X] T075 [US2] Implement `src/speakloop/feedback/report_builder.py` (Phase B form) — composes frontmatter + body sections: per-attempt metrics table, cross-attempt comparison paragraph, transcripts section; `grammar_patterns: []`, `generated_by_phase: B`; FR-010, FR-011, FR-012, FR-014 (no pronunciation); depends on T073, T074
- [X] T076 [P] [US2] Implement `src/speakloop/sessions/timer.py` — `rich.progress` countdown with `transient=True`; per-ordinal budget table 240/180/120 (research.md § "Timer / countdown UX"); FR-005, FR-006, FR-007 (early-exit key)
- [X] T077 [P] [US2] Implement `src/speakloop/sessions/abort.py` — SIGINT handler; removes `*.tmp` under `sessions_dir()`; sets a process-global event the coordinator polls; exit code 130 (FR-016)
- [X] T078 [US2] Implement `src/speakloop/sessions/coordinator.py` (Phase B form) — orchestrates state machine `listening → attempt_1 → attempt_2 → attempt_3 → analyzing → reporting → done` (data-model.md §3); ties `tts` + `audio.playback` + `audio.recorder` + `asr` + `metrics` + `feedback.report_builder` + `feedback.markdown_writer`; depends on T044, T047, T048, T066, T068, T069, T070, T071, T072, T075, T076, T077
- [X] T079 [US2] Extend `src/speakloop/cli/practice.py` for Phase B — drop `--listen-only` default to `false` once ASR is installed; call `coordinator.run_session(...)`; FR-005..FR-008
- [X] T080 [US2] Wire FR-009 pre-check in `cli/practice.py` — call `audio.devices.default_input()` before entering attempt phase; on `None`, print remediation pointing at `speakloop doctor` and exit 1
- [X] T081 [US2] Implement filename-collision disambiguation in `feedback/report_builder.py` (or a small helper) — `next_available_path(sessions_dir, date, question_id)` returns `…-q<id>.md` then `…-q<id>-2.md`, `-3.md`, … on collision (FR-017)

**Checkpoint (end of Phase B)**: User Story 2 is fully functional through to an **interim** Markdown report. Sessions write `generated_by_phase: B`, `grammar_patterns: []`. Story 1 + Story 3 + Story 2 (Phase B) together = Phase B ships.

### Tests for User Story 2 — Phase C (LLM grammar feedback)

> **⚠️ BLOCKED**: Tasks T082–T088 MUST NOT begin until `doc/research_methodology.md` is authored (Constitution Principle X; plan.md § Complexity Tracking). The seed-5 catalog (FR-013a) and the LLM analyzer prompt depend on that document.

- [X] T082 [P] [US2] Unit test `tests/unit/llm/test_qwen_engine.py` — with `mlx_lm` monkeypatched to a stub returning a canned response, assert `generate(system, user)` returns the canned text; assert response contains NO `<think>` substring (Qwen3-8B leak guard, research.md § LLM); raises `LLMEngineError` on stub failure
- [X] T083 [P] [US2] Unit test `tests/unit/feedback/test_grammar_analyzer.py` — feed fixture 3-attempt transcripts that contain seed-5 examples (3sg-`s` drop, aux-be/do drop, definite-article omission, preposition substitution, possessor-order transfer); with mocked LLM, assert each seed pattern appears with ≥ 1 evidence quote drawn verbatim from a transcript (FR-013a, FR-013); a pattern absent from the transcripts is OMITTED, not reported as zero (FR-013c); an LLM-surfaced pattern with ≥ 2 occurrences appears labelled "other recurring pattern" (FR-013b)
- [X] T084 [US2] Integration test `tests/integration/test_phase_c_report.py` — full session with stub LLM returning a deterministic grammar-pattern payload → Markdown report has `grammar_patterns:` populated, `generated_by_phase: C`, evidence quotes match transcript substrings verbatim; SC-003 (report within 60 s of attempt 3 ending) measured on the mock path (target hardware verification deferred to Polish phase)

### Implementation for User Story 2 — Phase C

- [X] T085 [US2] Implement `src/speakloop/llm/qwen_engine.py` — the ONLY file in the repo that may `import mlx_lm` (Principle V, research.md § LLM); class `QwenEngine` implements `LLMEngine`; thinking-mode explicitly disabled in `mlx_lm` call (default for Qwen3.5 small series); strips any tokenizer-internal artefacts from output; depends on T014
- [X] T086 [US2] Implement `src/speakloop/feedback/grammar_analyzer.py` — seed-5 catalog (FR-013a) hard-coded; open-bucket via LLM call with system prompt derived from `doc/research_methodology.md`; surfaces additional patterns only when `occurrence_count >= 2` (FR-013b); never asks for or stores an L1 declaration (FR-013c); every finding includes ≥ 1 verbatim evidence quote (FR-013); depends on T085
- [X] T087 [US2] Extend `feedback/report_builder.py` for Phase C — populate `grammar_patterns`, set `generated_by_phase: C`; depends on T086
- [X] T088 [US2] Update `sessions/coordinator.py` for Phase C — call `grammar_analyzer` after metrics, before `report_builder`; SC-003 (report within 60 s of attempt 3 ending); depends on T086, T087

**Checkpoint (end of Phase C)**: User Story 2 fully delivered. Reports gain the Grammar patterns section with evidence quotes.

---

## Phase 6: User Story 5 — Discover and verify the installation (`speakloop doctor`) (Priority: P2) [Phase A]

**Goal**: User runs `speakloop --help` (works without models) and `speakloop doctor` (reports state of Python, models, audio in/out, sessions/ writability) with actionable remediation hints; non-zero exit on any FAIL.

**Independent Test**: On a machine with no models, `speakloop --help` exits 0 in < 2 s (SC-006). On a fully-set-up machine, `speakloop doctor` reports all PASS. Deliberately break each precondition (move a model file, deny mic permission, chmod `data/sessions/` to read-only) → each surfaces with remediation text and exit code is non-zero (SC-007, FR-024, FR-025, FR-026).

### Tests for User Story 5

- [X] T089 [P] [US5] Unit test `tests/unit/cli/test_doctor.py` — `CliRunner.invoke(app, ["doctor"])` on a fully-set-up `tmp_sessions_dir` + present-model fixture → exit 0 and output sections per `contracts/cli-commands.md` § "doctor"; break each precondition individually → exit non-zero and remediation hint present for the failing check (FR-025, FR-026); `--json` flag emits valid JSON parsable by `json.loads`
- [X] T090 [US5] Integration test `tests/integration/test_doctor_failure_modes.py` — exhaustive sweep across: missing model file, corrupt model (size mismatch via T035), no input device (monkeypatched `audio.devices`), no output device, read-only `sessions_dir` → assert every precondition is reported in a single run (SC-007)

### Implementation for User Story 5

- [X] T091 [US5] Implement `src/speakloop/cli/doctor.py` — sections per FR-024: Python runtime, models (per-model status via `installer.validator`), default output device, default input device, `sessions_dir()` writability; `rich`-rendered table by default + `--json` for scripting; exits non-zero on any FAIL (FR-026) with per-line remediation text (FR-025); depends on T035, T067

**Checkpoint**: User Story 5 fully functional and SC-007 verifiable.

---

## Phase 7: User Story 4 — Review progress across past sessions (`speakloop trends`) (Priority: P2) [Phase C]

**Goal**: User runs `speakloop trends` and sees an aggregated terminal summary across past Markdown reports: total sessions, date range, fluency-metric trajectories (attempt-3 across sessions), and a top-N grammar-pattern ranking.

**Independent Test**: With ≥ 3 fixture report files under `data/sessions/`, `speakloop trends` renders a `rich` table with totals, per-metric trajectory, and ranked patterns. SC-008 (≤ 60 terminal lines on 10 sessions) verified. SC-010 (14 distinct entries for 14 sessions) verified. Empty `data/sessions/` → helpful empty-state message + exit 0 (FR-033). Malformed file → skipped with single warning (FR-034).

### Tests for User Story 4

- [X] T092 [P] [US4] Unit test `tests/unit/trends/test_reader.py` — `read_reports(dir)` uses `python-frontmatter`; non-speakloop Markdown skipped silently; malformed frontmatter skipped with one warning naming the file (FR-034); date filter `since` honored
- [X] T093 [P] [US4] Unit test `tests/unit/trends/test_aggregator.py` — `total_sessions`, `date_range`, `metric_series` (attempt-3 values, data-model.md §8), `pattern_ranking` top-N sorted descending; ties broken deterministically (label asc)
- [X] T094 [P] [US4] Unit test `tests/unit/trends/test_renderer.py` — `rich`-rendered table; empty input → empty-state paragraph pointing at `speakloop practice` (FR-033) + exit 0; line-count budget ≤ 60 for a 10-session input (SC-008)
- [X] T095 [US4] Integration test `tests/integration/test_phase_c_trends.py` — commit 3 fixture reports under `tests/fixtures/sessions/` (Phase-B and Phase-C mix); `CliRunner.invoke(app, ["trends", "--sessions-dir", <fixtures>])` → exit 0; output contains expected totals + top-N patterns; SC-010 verified by extending the fixture set to 14 dates

### Implementation for User Story 4

- [X] T096 [P] [US4] Implement `src/speakloop/trends/reader.py` — `python-frontmatter.load`; skip non-speakloop / malformed files with one grouped notice (FR-034); honors `--since` filter
- [X] T097 [P] [US4] Implement `src/speakloop/trends/aggregator.py` — `total_sessions`, `date_range`, `metric_series` (attempt-3), `pattern_ranking` (data-model.md §8)
- [X] T098 [US4] Implement `src/speakloop/trends/renderer.py` — `rich` tables / sparklines; empty-state (FR-033); SC-008 budget; depends on T097
- [X] T099 [US4] Implement `src/speakloop/cli/trends.py` — typer subcommand with `--sessions-dir`, `--top-patterns`, `--since` flags per `contracts/cli-commands.md`; wires reader → aggregator → renderer; depends on T096, T097, T098

**Checkpoint**: User Story 4 fully functional.

---

## Phase 8: User Story 6 — Add or edit personal Q&A content (Priority: P3) [Phase A]

**Goal**: User edits `~/.speakloop/qa.yaml` and on next session sees the new entry. Invalid YAML reports file + line. Missing required field reports entry id + field name.

**Independent Test**: Starter Q&A in place. Add a new entry → rerun → entry appears in picker. Corrupt the file with a YAML syntax error → next run prints file path + line number + remediation + exit non-zero (FR-029). Delete `ideal_answer` from an entry → next run reports the entry id and the missing `ideal_answer` field (FR-030).

> Most of this story's behavior is exercised by the loader tests (T037) and the starter file (T045) under User Story 1. Tasks here are the user-visible round-trip + remaining error-path assertions.

### Tests for User Story 6

- [X] T100 [P] [US6] Integration test `tests/integration/test_qa_edit_round_trip.py` — write `qa.yaml` via `tmp_path`, run picker (with TTS/playback mocked) → fixture entries listed; append a new valid entry; rerun picker → new entry now selectable
- [X] T101 [P] [US6] Unit test `tests/unit/content/test_loader_errors.py` — `invalid-syntax.yaml` raises with message containing exact `file_path:line_number:` prefix and a one-line remediation suggestion (FR-029); `missing-field.yaml` raises naming the entry id and `ideal_answer` exactly as the missing field (FR-030)

### Implementation for User Story 6

- [X] T102 [US6] Extend `src/speakloop/content/loader.py` error formatting to exactly match FR-029 (`<path>:<line>:` prefix + remediation hint) and FR-030 (entry id + missing field name); depends on T044

**Checkpoint**: All user stories independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T103 [P] Finalize top-level `CLAUDE.md` with the complete module list and links to every per-module `CLAUDE.md` (Principle XI)
- [X] T104 [P] Update `README.md` with install command, link to `quickstart.md`, and a note documenting the Phase-A-only and Phase-B-only install paths so partial-phase users have a useful tool (Principle XII)
- [ ] T105 Run `quickstart.md` end-to-end on a clean macOS arm64 environment — verify SC-001 (≤ 30 minutes to practice menu excluding download bytes), SC-006 (≤ 2 s `--help`) **— DEFERRED to real-hardware verification; SC-006 verified in-process (`uv run speakloop --help` ≈ 0.25 s).**
- [X] T106 SC-009 verification: with all models present, disable network (e.g., `networkdown` shell function or unplug Wi-Fi), run `speakloop practice` and `speakloop trends` end-to-end; assert NO outbound network call observed (FR-023, FR-037) **— Verified via `tests/integration/test_offline_after_install.py` (socket monkeypatch fixture): `practice --listen-only`, `trends`, and `doctor` all complete with zero socket construction.**
- [ ] T107 [P] SC-003 performance measurement on target M-series hardware — full Phase-C session; assert report is written within 60 s of attempt 3 ending; tune `mlx_lm` generation params (`max_tokens`, temperature) in `qwen_engine.py` if necessary **— DEFERRED to real-hardware verification; SC-003 verified on the mock path in T084 (< 1 s).**
- [X] T108 [P] Final `ruff check` + `ruff format` sweep; ensure all module `__init__.py` re-exports match the public surface documented in each `CLAUDE.md`
- [X] T109 Constitution Principle V audit: `grep -rE '^(from|import) (kokoro_mlx|mlx_audio|parakeet_mlx|mlx_lm)' src/speakloop/` MUST return exactly three matches — one in `tts/kokoro_engine.py`, one in `asr/parakeet_engine.py`, one in `llm/qwen_engine.py`; fail loudly otherwise

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories.**
- **User Stories (Phase 3+)**: All depend on Foundational completion.
  - **US3 → US1**: Once Foundational is done, US3 (installer) can be built in parallel with US1 (listen) because US1 tests use stub engines. End-to-end Phase A delivery integrates the two.
  - **US2 Phase B**: Depends on US1's `tts` + `audio.playback` + `content` + the installer (US3 for ASR model).
  - **US2 Phase C**: Depends on US2 Phase B **and** on `doc/research_methodology.md` being authored (plan.md § Complexity Tracking — tasks T082..T088 are BLOCKED until then).
  - **US4 (trends)**: Depends on US2 Phase B reports existing on disk (or fixture reports under `tests/fixtures/sessions/`).
  - **US5 (doctor)**: Depends on `installer/validator.py` (T035) and `audio/devices.py` (T067) for full coverage.
  - **US6**: Mostly bundled inside US1's loader; T102 finalises error-message format.
- **Polish (Phase 9)**: Depends on all stories being complete.

### Within Each User Story

- Tests are written **first** and **MUST fail** before the matching implementation lands (Constitution Dev Guidelines + research.md § Testing).
- Models (dataclasses, schemas) before services.
- Services before CLI wiring.
- Story complete before moving to the next priority.

### Parallel Opportunities

- All Setup tasks marked `[P]` can run in parallel.
- All Foundational tasks marked `[P]` can run in parallel within Phase 2.
- Once Foundational completes, **US1**, **US3**, and **US5** can be developed in parallel (different files, no cross-story dependencies).
- Within US2 Phase B, all metric modules (T069–T072) and all unit tests (T053–T060) are independent and `[P]`.
- US4 (trends) tasks T092–T094 and T096–T097 are independent and `[P]`.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Independent files — launch in parallel:
Task: "Implement TTSEngine Protocol in src/speakloop/tts/interface.py"           # T012
Task: "Implement ASREngine Protocol in src/speakloop/asr/interface.py"           # T013
Task: "Implement LLMEngine Protocol in src/speakloop/llm/interface.py"           # T014
Task: "Commit fixture WAVs under tests/fixtures/wav/tts/"                        # T017
Task: "Commit fixture WAVs under tests/fixtures/wav/recordings/"                 # T018
Task: "Commit fixture transcripts under tests/fixtures/transcripts/"             # T019
Task: "Commit fixture Q&A YAMLs under tests/fixtures/qa/"                        # T020
```

## Parallel Example: User Story 2, Phase B — fluency metrics

```bash
# All metric modules are independent files — launch in parallel:
Task: "src/speakloop/metrics/speech_rate.py + test_speech_rate.py"               # T069, T053
Task: "src/speakloop/metrics/pauses.py + test_pauses.py"                         # T070, T054
Task: "src/speakloop/metrics/fillers.py + test_fillers.py"                       # T071, T055
Task: "src/speakloop/metrics/self_corrections.py + test_self_corrections.py"     # T072, T056
```

---

## Implementation Strategy

### MVP first — Phase A (Stories 1 + 3 + 5 + 6)

1. Complete Phase 1 (Setup).
2. Complete Phase 2 (Foundational) — `--help` already works without models (FR-018, SC-006).
3. Build **US3** (installer) and **US1** (listen) in parallel; integrate.
4. Layer **US5** (doctor) and **US6** (Q&A error messages) on top.
5. **STOP and VALIDATE Phase A**: `speakloop practice --listen-only` end-to-end on a fresh machine. Phase A ships as a complete shadowing-practice tool (Constitution Principle XII).

### Incremental delivery

1. **Phase A ships** after Stories 1 + 3 + 5 + 6 land. Useful even if B and C never merge.
2. **Phase B**: Add Story 2 Phase B (T051–T081). Sessions now produce interim Markdown reports with metrics. Phase B ships as a complete practice-with-feedback tool.
3. **Phase C**: After `doc/research_methodology.md` is authored, unblock T082–T088 and complete Story 2 Phase C. Add Story 4 (trends). v1 complete.

### Hard blocker

- **`doc/research_methodology.md` must exist on disk before T082 begins.** This is the Constitution Principle X tracked exception in plan.md § Complexity Tracking. Phase A and Phase B are fully unblocked.

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete tasks.
- `[Story]` label maps each task to a spec.md user story (US1..US6) for traceability.
- Tests use **committed fixtures** under `tests/fixtures/` only — **no live model calls in tests** (Constitution Dev Guidelines, research.md § Testing).
- Every engine wrapper file (`kokoro_engine.py`, `parakeet_engine.py`, `qwen_engine.py`) is the ONLY file in the codebase allowed to import its engine package (Principle V; audited by T109).
- Atomic Markdown writes (T074) are the load-bearing mechanism behind FR-016 / SC-005 — keep the test (T058) green forever.
- Verify each test fails before implementing.
- Commit after each task or logical group.
- Stop at any checkpoint to validate the story independently.
