---
description: "Task list for 016-pronunciation-drills"
---

# Tasks: Pronunciation Drills

**Input**: Design documents in `specs/016-pronunciation-drills/` (plan.md, spec.md, research.md,
data-model.md, contracts/, quickstart.md)

**Tests**: Included. The guardrails require new tests (gate, concurrent drill+feedback merge, aria2
fetch path, no-model-load-on-`--help`, import isolation). Heavy model + mic are never touched in
tests — the wav2vec2 scorer is faked and the GOP/alignment math is tested with synthetic posteriors.

**Organization**: by user story. **MVP = US1 (drill block) + US3 (safety gate)** — inseparable core.
US2 (report), US4 (download), US5 (docs) support them.

## Path conventions

Single project. New module: `src/speakloop/pronunciation/`. Tests under `tests/unit/...` and
`tests/integration/...`. Every behavior-changing task updates its owning CLAUDE.md **in the same
commit** (constitution v1.1.0 anti-rot).

---

## Phase 1: Setup (shared prerequisites)

- [ ] T001 Declare new runtime deps in `pyproject.toml`: add `transformers>=4.34` (Apache-2.0; already transitive — declare because we import it directly) and `psutil>=5.9` (BSD-3, RAM gate), with the same "declared because imported directly" comment style as `scipy`/`onnxruntime`. Do NOT touch `torch`/`torchaudio` pins. Run `uv lock` and confirm torch stays 2.8.x / torchaudio 2.8.x.
- [ ] T002 Create the module package skeleton: `src/speakloop/pronunciation/__init__.py` (lazy public surface, NO engine imports at module scope), and a placeholder `src/speakloop/pronunciation/CLAUDE.md` (filled in T040). Add the module row to the root CLAUDE.md module table (20th module) in the same commit.
- [ ] T003 [P] Add the two additive `loop.yaml` keys in `src/speakloop/config/loop_config.py`: `pronunciation_drills` (default `"auto"`, validated against `("auto","on","off")`) and `pronunciation_min_free_mb` (default `4500`, `max(0,int)`). Add fields to `LoopConfig`, default constants, and parse branches in `load()`. Update the `loop.yaml` key table in `src/speakloop/config/CLAUDE.md` in the same commit.
- [ ] T004 [P] Extend the import-isolation guards for the new heavy packages: add `torch` and `transformers` mapped to `pronunciation/wav2vec2_engine.py` in `tests/unit/asr/test_engine_import_isolation.py` (ENGINE_PACKAGES), and add `torch`,`transformers` to the leak set in all three subprocess checks of `tests/integration/test_help_without_models.py`. (These guard the work done in Phase 2/4; they fail until the wrapper exists, which is fine — they pass once imports stay function-local.)

**Checkpoint**: deps resolve, package imports cleanly, config keys parse, guards updated.

---

## Phase 2: Foundational (blocking building blocks for all stories)

These are pure/deterministic units consumed by US1/US2/US3. No engine package loads here except
inside the wav2vec2 wrapper's `_load()`.

- [ ] T005 Define `src/speakloop/pronunciation/interface.py`: `PronunciationScorer` Protocol, `DrillResult`, `PhoneFlag` dataclasses, `PronunciationError` (per contracts/pronunciation-module.md + data-model §2). No engine imports.
- [ ] T006 [P] Implement `src/speakloop/pronunciation/gop.py` — pure-numpy CTC forced alignment (`forced_align`), `gop_scores`, `top_competitor` (contracts/pronunciation-module.md §gop.py). No torch/transformers; numpy only.
- [ ] T007 [P] Tests `tests/unit/pronunciation/test_gop.py`: build SYNTHETIC `[T,vocab]` log-posterior matrices; assert monotonic non-overlapping spans cover the sequence; planting competitor mass at a target token lowers its GOP and makes `top_competitor` return the planted phone. No model loaded.
- [ ] T008 [P] Author `src/speakloop/pronunciation/drill_bank.yaml` — curated contrasts (w/r, v/w, θ/s, ð/d, ɪ/iː, l/ɹ, …) + base drills with bundled canonical phoneme sequences (model symbol set), `target_indices`, and minimal-pair follow-ons (data-model §1). Phoneme symbols validated against the model `vocab.json` at authoring time (document the method in research; do NOT fetch at runtime).
- [ ] T009 Implement `src/speakloop/pronunciation/drill_bank.py` — `load_drill_bank()`, `DrillBank.base_drills()`, `.next_drills(contrast_id, exclude_ids, max=2)`, `.contrast(id)`, `Drill`/`Contrast` types (loads the bundled YAML via `Path(__file__).parent`, mirroring `feedback/cloud_prompt.py`). Bounded routing (FR-024).
- [ ] T010 [P] Tests `tests/unit/pronunciation/test_drill_bank.py`: bank loads; every drill references a known contrast; `target_indices` in range; `next_drills` is bounded and excludes already-seen ids; (when a tiny vocab fixture is supplied) canonical symbols exist in vocab.
- [ ] T011 Implement `src/speakloop/pronunciation/wav2vec2_engine.py` — the ONLY file importing `torch` + `transformers` (function-local in `_load()`); `build_scorer()` factory; `Wav2Vec2Scorer.score(...)` per contract (audio→logits→log-softmax→`gop.forced_align`→`PhoneFlag`s; `not_captured` on near-silence; `error` on failure, never raises). CPU inference, `torch.no_grad()`. Reads model from `manifest.WAV2VEC2_PRONUNCIATION.local_path`.
- [ ] T012 [P] Implement `src/speakloop/pronunciation/feedback.py` — `render_drills_section(drills_dict) -> str|None`, detection-led + diagnosis hedged (data-model §5, FR-009); pure formatter, no engine imports.
- [ ] T013 [P] Tests `tests/unit/pronunciation/test_feedback_calibration.py`: a confident-detection-but-uncertain-diagnosis flag renders the detection plainly and either omits the substitution or labels it a suggestion ("may", "likely") — never as a verdict; empty items → `None`.
- [ ] T014 Add the additive `pronunciation_drills: dict | None = None` field to `Session` in `src/speakloop/feedback/frontmatter.py`; emit in `dump()` only when truthy; read back in `parse()` as a plain dict; `SCHEMA_VERSION` stays 1. Note it is DISTINCT from the existing `pronunciation_flags` (010 mishearings). Update `src/speakloop/feedback/CLAUDE.md` (frontmatter field list) in the same commit.

**Checkpoint**: GOP math, drill bank, scorer wrapper, calibrated wording, and the frontmatter slot
exist and are unit-tested (no model). `speakloop --help` still loads no engine package (T004 green).

---

## Phase 3: User Story 3 — Safety gate (Priority P1, inseparable from US1) 🎯 MVP

**Goal**: Never load the pronunciation model when unsafe (local engine resident or low RAM); explain
why; offer a freeze-warned override. **Independent test**: simulate local-Qwen / low-RAM → decision is
UNSAFE, no scorer is constructed; cloud + RAM-ok → SAFE.

- [ ] T015 [US3] Implement `src/speakloop/pronunciation/gate.py` — `SafetyDecision` dataclass + `assess_safety(engine, *, min_free_mb, available_mb=None)` per contracts/safety-gate.md. `local` engine → always UNSAFE; cloud + `available>=min` → SAFE; cloud + low → UNSAFE; psutil import function-local with graceful fallback (unknown RAM on a cloud engine → SAFE-cautious). Plain-language reasons always include a remediation hint.
- [ ] T016 [P] [US3] Tests `tests/unit/pronunciation/test_gate.py`: full matrix — `engine="local"` is UNSAFE even with huge RAM (SC-001); cloud below/at/above threshold; psutil-absent fallback; reasons contain a remediation hint; `assess_safety` never imports/loads the model.
- [ ] T017 [US3] Wire the gate decision + messaging into `src/speakloop/cli/practice.py`: a `_resolve_pronunciation_drills(engine_choice, console, *, setting, input_fn, override_confirm)` helper that reads the `pronunciation_drills` setting (+ `--drills/--no-drills` override), calls `assess_safety`, and returns a decision object the loop uses. `off` → short-circuit (no gate). UNSAFE → print reason; interactive + auto/on → offer freeze-warned `[y/N]` (default N) override; SAFE → continue to the offer/provision step (US1/US4). Add `--drills/--no-drills` (`Optional[bool]`) to the `practice` command in `cli/main.py`.
- [ ] T018 [P] [US3] Tests `tests/unit/cli/test_pronunciation_gate_wiring.py`: with `engine=local` and default setting, `_resolve_pronunciation_drills` returns "skip" and never builds a scorer; `off` → no gate call; unsafe + injected override-confirm "yes" → proceeds; non-interactive never overrides. Use injected `input_fn`/fakes (no real prompt, no model).

**Checkpoint**: the gate is authoritative and tested; the dangerous override is reachable only by an
explicit interactive "yes". MVP-safety is in place.

---

## Phase 4: User Story 1 — Read-aloud drill block, concurrent with feedback (Priority P1) 🎯 MVP

**Goal**: Run user-paced read-aloud drills while feedback runs in the background; merge into one
report shown after both finish. **Independent test**: with a FAKE scorer + fake `record_fn` +
fake key reader, the drill block runs, the backgrounded `_analyze` completes, and the report contains
both the grammar output and the pronunciation block; report appears only after both finish.

- [ ] T019 [US1] Add `quiet: bool = False` to `coordinator._analyze(...)` in `src/speakloop/sessions/coordinator.py`: when quiet, the `_analyzing(...)` spinners become no-op context managers (plain, no live `rich` display); degradation `console.print`s still allowed. Keep the non-quiet path byte-identical to today.
- [ ] T020 [US1] Implement `coordinator._run_pronunciation_drills(question, *, drills, record_fn, asr_engine?, tts_engine, play_fn, context, scratch_dir, early_exit_event, console, key_reader, ui_sleep) -> dict | None` mirroring `_run_warmup`: no-op (None) unless a scorer + drill bank are injected; present each base drill (display text + optional TTS prompt), record read-aloud via `_record_stage`, score via the injected scorer, show calibrated per-item feedback, route ≤2 follow-on minimal-pair drills for a flagged contrast (FR-006/024); `not_captured`/`error` degrade gracefully (FR-007); check `abort.abort_event` between items; discard drill WAVs from scratch after scoring.
- [ ] T021 [US1] In `coordinator.run_session(...)`, add a `pronunciation_drills` param (the injected bundle: scorer + bank + engine_note) and rework the analysis stage: when drills are permitted and not aborted, start `_analyze(..., quiet=True)` in a background daemon thread, run `_run_pronunciation_drills(...)` on the main thread, then JOIN the thread (under a single `working(ANALYZING, "Finishing your feedback…")` spinner if still running) and proceed to report assembly. When no drills, keep today's inline `_analyze(...)` path unchanged. Preserve the abort-before-analysis pending-report path.
- [ ] T022 [US1] Build + inject the scorer in `src/speakloop/cli/practice.py`: when the gate (T017) permits and the user accepts, call `installer.ensure_pronunciation_model(...)` (US4) then `pronunciation.build_scorer()` + `load_drill_bank()`; assemble the bundle once before the session loop and pass it into every `run_session(...)` (reused on REPLAY, like the engines). Engine imports stay function-local. Skip cleanly (bundle=None) on decline/unsafe/error.
- [ ] T023 [US1] Add the pronunciation result to the `Session` in `run_session`: set `pronunciation_drills=drills_dict` (the dict from T020) only when present; ensure it flows into `report_builder.build(...)`. Update `src/speakloop/sessions/CLAUDE.md` (new `_run_pronunciation_drills` + background-analysis-concurrent-with-drills note, O6 byte-identical still holds) in the same commit.
- [ ] T024 [US1] Integration test `tests/integration/test_drills_concurrent_with_feedback.py`: inject a fake scorer (deterministic `DrillResult`s incl. a flagged contrast), a fake `record_fn`, a `FakeKeyReader`, and a fake grammar_analyzer that sleeps briefly; assert (a) the drill block produced items, (b) the backgrounded analysis completed and its grammar output is in the report, (c) the pronunciation section is present, (d) the report is written after both — and no real model/mic is touched.

**Checkpoint**: end-to-end MVP (US1+US3) works with fakes; real-model path is manual-smoke (live audio).

---

## Phase 5: User Story 2 — Calibrated pronunciation report section (Priority P2)

**Goal**: Additive, honestly-calibrated Pronunciation section; byte-identical report when absent.

- [ ] T025 [US2] Add `_pronunciation_drills_section(session)` to `src/speakloop/feedback/report_builder.py` (delegates to `pronunciation.render_drills_section`), rendered AFTER the interview-loop sections and BEFORE the transcripts; returns None when `session.pronunciation_drills` is absent. Update `src/speakloop/feedback/CLAUDE.md` report-order note in the same commit.
- [ ] T026 [P] [US2] Integration test `tests/integration/test_drills_additive_byte_identical.py`: a session WITHOUT drills renders a report byte-for-byte identical to the pre-feature builder output (complements `test_analysis_equivalence.py`); a session WITH drills adds exactly the new section and changes nothing else (grammar/coaching/coverage/transcripts unchanged).
- [ ] T027 [P] [US2] Confirm `tests/integration/test_analysis_equivalence.py` still passes (serial==concurrent byte-identical; pronunciation absent in that fixture).

**Checkpoint**: report section renders calibrated; no-drills reports unchanged (SC-003).

---

## Phase 6: User Story 4 — Opt-in download via the existing aria2 flow (Priority P2)

**Goal**: Register + fetch the model only on first opt-in, through the resilient downloader; never
download for a user who skips drills.

- [ ] T028 [US4] Extend `src/speakloop/installer/manifest.py`: add optional `Model.weight_files: tuple[str,...] | None = None`; add `WAV2VEC2_PRONUNCIATION` (facebook/wav2vec2-lv-60-espeak-cv-ft, ~1.262 GB, `weight_files=("pytorch_model.bin",)`), NOT in any `PHASE_*_MODELS` list. Update `src/speakloop/installer/CLAUDE.md` (constants + weight_files) in the same commit.
- [ ] T029 [US4] Extend `src/speakloop/installer/downloader.py`: in `_download_via_aria`, use `model.weight_files` when set else `discover_shards(local_dir)`; add `"preprocessor_config.json"` to `META_FILES`. Byte-identical for all existing models (weight_files=None). Update `installer/CLAUDE.md` (downloader note) same commit.
- [ ] T030 [US4] Add `installer.ensure_pronunciation_model(*, console, consent_fn, download_fn, input_fn)` in `src/speakloop/installer/__init__.py` mirroring `ensure_models` for the single model (validate→caffeinate→consent→download→re-validate; raises InstallDeclinedError/InstallFailedError). Export it.
- [ ] T031 [P] [US4] Tests `tests/unit/installer/test_pronunciation_model.py` (contracts/downloader-extension.md §Tests): weight_files value + not-in-phase; fake aria runner requests `pytorch_model.bin` not `model.safetensors`; `preprocessor_config.json` in META_FILES; `ensure_pronunciation_model` honors decline + a fake download_fn + re-validates; existing-model shard discovery unchanged.
- [ ] T032 [P] [US4] Add a "Pronunciation drills" section to `src/speakloop/cli/doctor.py` (`_pronunciation()` → list[CheckRow]): model present/absent (optional — never FAILs the exit code), the `pronunciation_drills` setting value, and a gate estimate for the active engine; append in `_collect()`. Update `cli/CLAUDE.md` doctor-sections note in the same commit.
- [ ] T033 [P] [US4] Test `tests/unit/cli/test_doctor_pronunciation.py`: the pronunciation rows render and NEVER produce a FAIL (model absent ⇒ WARN/OK info row), so a drills-skipping user's `doctor` still exits 0.

**Checkpoint**: opt-in download works through the aria2 path; never-opted-in users download nothing
(SC-004); doctor reports it as optional.

---

## Phase 7: User Story 5 — Docs (Priority P3)

- [ ] T034 [US5] Add a "Pronunciation drills" section to `README.md`: what it does, opt-in + engine/memory-gated + read-aloud only, the `pronunciation_drills` auto/on/off setting + `pronunciation_min_free_mb`, the `--drills/--no-drills` flags, the freeze-warned override, and that `resume`/`--listen-only` don't run drills. Mirror `quickstart.md`.
- [ ] T035 [P] [US5] Finalize `doc/research_pronunciation.md`: keep the existing domain research and append a short "Implementation decisions (016)" addendum pointing to `specs/016-pronunciation-drills/research.md` (bundled-phoneme + pure-numpy-GOP + CPU + gate substitutions). Update the root CLAUDE.md "Pointers" engine-research line to include `research_pronunciation.md` in the same commit.
- [ ] T036 [P] [US5] Update the root CLAUDE.md `Commands` block: add the `--drills/--no-drills` flag to the `practice` line and a one-line note on the engine/memory gate; confirm the SPECKIT block (already updated) and module table (T002) are consistent.

**Checkpoint**: feature is discoverable; research is in-repo (Principle X).

---

## Phase 8: Polish & cross-cutting (final verification)

- [ ] T037 Fill `src/speakloop/pronunciation/CLAUDE.md` (≤200 lines): purpose, public interface, the function-local torch/transformers rule, gop/gate/drill_bank/feedback file map, invariants (no runtime g2p/NLTK/network; CPU inference; never raises into the session), pointers. (T002 placeholder → final.)
- [ ] T038 Sweep all touched module CLAUDE.md for anti-rot accuracy (`sessions/`, `installer/`, `config/`, `feedback/`, `cli/`, `pronunciation/`, root) — each behavior change is reflected; run `uv run pytest tests/integration/test_context_file_budget.py` (≤200 lines each).
- [ ] T039 Run gates: `uv run pytest tests/integration/test_help_without_models.py tests/unit/asr/test_engine_import_isolation.py tests/integration/test_path_portability_audit.py tests/integration/test_analysis_equivalence.py tests/integration/test_no_network_during_session.py` — all green (no `/Users/...` paths; no engine load at `--help`; offline session; byte-identical analysis).
- [ ] T040 Run the full suite `uv run pytest`; record pass count vs the pre-feature baseline; fix any regressions. Confirm the new tests (T007, T010, T013, T016, T018, T024, T026, T031, T033) pass.

---

## Dependencies & execution order

- **Phase 1 (Setup)** → blocks everything.
- **Phase 2 (Foundational)** → blocks US1/US2/US3 (provides interface/gop/drill_bank/scorer/wording/frontmatter).
- **US3 (Phase 3)** → small, independent; do **first** (it gates US1). Depends on T003 (config) + T015 only.
- **US1 (Phase 4)** → depends on Phase 2 (scorer/bank) + US3 (gate) + US4's `ensure_pronunciation_model` (T030) for the real build path (T022); the integration test (T024) uses fakes and needs only Phase 2 + coordinator changes.
- **US2 (Phase 5)** → depends on T014 (frontmatter) + T012 (wording) + T020/T023 (drills dict shape).
- **US4 (Phase 6)** → independent of US1/US2 except T030 is consumed by T022.
- **US5 (Phase 7)** → after behavior lands.
- **Phase 8** → last.

Suggested implementation order honoring MVP-first + the inseparable core:
**Phase 1 → Phase 2 → US3 → US4(T028–T031) → US1 → US2 → US4(T032–T033 doctor) → US5 → Phase 8.**
(US4's download helper T030 is pulled before US1 so the real scorer-build path in T022 is wired.)

## Parallel opportunities

- Phase 1: T003, T004 in parallel after T002.
- Phase 2: T006/T007 (gop), T008→T009→T010 (bank), T012/T013 (wording), T014 (frontmatter) — gop, bank, wording, frontmatter are independent files → parallel; T011 (wrapper) after T005/T006.
- Phase 3: T016 ∥ after T015.
- Phase 6: T031, T032, T033 ∥ after T028–T030.
- Phase 7: T034/T035/T036 ∥.

## MVP scope

**US1 + US3** (drill block + safety gate) delivered with the supporting frontmatter/report so a cloud
user gets safe, calibrated drills merged into the report, and a local-engine user is safely declined.
US4 (download) is required for the real-model path; US2 (report) and US5 (docs) round it out.
