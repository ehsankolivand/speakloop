---
description: "Task list for 017-pronunciation-trainer implementation"
---

# Tasks: Pronunciation Trainer (hear → say → see → retry)

**Input**: Design documents from `specs/017-pronunciation-trainer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the spec/guardrails explicitly require tests for hear-first ordering, bounded
retry, the standalone RAM-only gate, weak-sound prioritisation, the byte-identical guarantee, and the
live TTS-through-scorer harness. Heavy model + mic + TTS stay faked in the default suite; the
correctness harness is a self-skipping `live_pron` test.

**Base**: branched off `016-pronunciation-drills` (016 not yet on main — see plan Notes). Reuses the
entire 016 `pronunciation/` module.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no incomplete-task dependency)
- **[Story]**: US1..US5 (user-story phases only)

---

## Phase 1: Setup

- [x] T001 Register the `live_pron` pytest marker in `pyproject.toml` `[tool.pytest.ini_options].markers` (alongside `live_asr`/`live_llm`/`live_download`: "thin live smoke test rendering every bundled drill through the REAL Kokoro TTS + wav2vec2 scorer; skips when the model/TTS are absent; excluded from the default suite").
- [x] T002 Add config keys `pronunciation_tts_playback` (bool, default `True`) and `pronunciation_retries` (int, default `1`, clamp `[0,3]`) to `src/speakloop/config/loop_config.py` (constants + `LoopConfig` fields + `load()` parse branches) and update the key table in `src/speakloop/config/CLAUDE.md` — same commit.

---

## Phase 2: Foundational (blocking prerequisites — pure loop core shared by US1/US3/US4)

- [x] T003 Create `src/speakloop/pronunciation/drill_runner.py`: pure, UI-agnostic `run_drill_item(drill, *, contrast, scorer, speak, record, key_reader, console, scratch_dir, retries=1, tts_on=True, is_follow_on=False) -> dict` (hear-first + replay-on-demand + bounded automatic retry + improvement detection + calibrated live prints via `pronunciation.feedback`) and `select_drills(bank, *, weak_contrasts, max_base) -> list[Drill]` and `DrillQuit(PronunciationError)` — per `contracts/drill-runner.md`. Import NO engine package and NO `sessions`/`tts`/`audio`.
- [x] T004 Export `run_drill_item`, `select_drills`, `DrillQuit` from `src/speakloop/pronunciation/__init__.py` (`__all__`).
- [x] T005 Extend `src/speakloop/pronunciation/feedback.py` with additive retry-outcome wording (per-item "On retry: better — that sound is clear now ✓" / "still a little off") and a "tricky sounds" summary line; keep detection-led + hedged (FR-006). Render only when the data is present (byte-identical when absent).
- [x] T006 [P] Unit test `tests/unit/pronunciation/test_drill_runner.py`: TTS spoken before record (fake `speak` records call order); bounded retry capped by `retries` with an always-flagging fake scorer; improvement reported when the retry clears; graceful degrade when `tts_on=False`/`NullKeyReader`; `DrillQuit` on `q`. No model/mic/tty.
- [x] T007 [P] Unit test `tests/unit/pronunciation/test_feedback_retry_wording.py`: retry/tricky-sounds wording is detection-led + hedged and is omitted when absent.

---

## Phase 3: User Story 1 — Hear it, say it, see it, retry it (Priority: P1) 🎯 MVP

**Goal**: the interview drill block plays the target first, allows replay, and gives a bounded retry on
a flagged item — degrading to exactly 016 when no TTS/interactivity is present.

**Independent test**: with a fake TTS/play + always-flagging scorer + interactive `FakeKeyReader`,
confirm the target is spoken before recording, a flagged item retries within the budget, the
improvement is shown, and a non-interactive run behaves like 016.

- [x] T008 [US1] Rewire `src/speakloop/sessions/coordinator.py` `_run_pronunciation_drills`: build a `speak(text)` closure from the injected `tts_engine`/`play_fn` (no-op when either is `None`) and a `record(wav, label)` closure from `_record_stage`; call `pronunciation.run_drill_item` for each base + follow-on drill (preserving the 016 bounded follow-on routing); pass `retries`/`tts_on` from config; catch `DrillQuit` to stop asking for more. Extend the summary with `retried`/`improved_on_retry`/`tricky_sounds` (data-model §3).
- [x] T009 [US1] Thread the new inputs into the drill block: pass `tts_engine`, `play_fn`, and the resolved `pronunciation_tts_playback`/`pronunciation_retries` from `run_session` into `_run_pronunciation_drills` (read config in `run_session` or pass through from the CLI). Keep the no-bundle path byte-identical (no behaviour change when `pronunciation_drills is None`).
- [x] T010 [US1] Update `src/speakloop/sessions/CLAUDE.md`: the drill block now hears-first + bounded-retry via `pronunciation.run_drill_item`; note TTS/play are injected and no-op in tests; concurrency + byte-identical guarantees unchanged — same commit.
- [x] T011 [P] [US1] Integration test `tests/integration/test_drill_hear_first_and_retry.py`: fake `tts_engine`/`play_fn` record that the target plays before the (fake) recorder runs; an always-flagging fake scorer + interactive `FakeKeyReader` drives one bounded retry; assert the report shows the retry outcome and respects `pronunciation_retries`.
- [x] T012 [P] [US1] Confirm `tests/integration/test_drills_concurrent_with_feedback.py` still passes unchanged (non-interactive `NullKeyReader`, no TTS → 016 behaviour: no hear-first, no retry, `with_flags >= 1`). Adjust only if a genuine signature change requires it (document why).

**Checkpoint**: US1 is the MVP — a working hear → say → see → retry loop in the interview session.

---

## Phase 4: User Story 2 — Practise full sentences (Priority: P2)

**Goal**: sentence base drills with bundled offline canonical phonemes; words become follow-ons; a live
harness validates every canonical sequence.

**Independent test**: base drills are sentences (>1 word); a flag routes into word follow-ons; the
`live_pron` harness scores every bundled drill clean on a model-equipped machine.

- [x] T013 [US2] Expand `src/speakloop/pronunciation/drill_bank.yaml`: add sentence base drills (`is_base: true`, flat per-word `canonical` in the model symbol set with no separator token, `targets` at the contrast phone) for the primary 016 contrasts (v_w, w_r, th_s, th_d, ih_iy, l_r); keep the 016 words as follow-ons (`is_base: false`); update the header comment to explain the flat-concatenation rule (research D3). Compose sentences from already-validated word sequences + simple connectives; place the contrast word-initial.
- [x] T014 [US2] Add `tests/live_pron_test.py` (marker `live_pron`, self-skipping via `importorskip` + model-presence check): for every drill in `load_drill_bank()`, render `drill.prompt` with the real `KokoroEngine`, score with `build_scorer()`, assert `status == "scored"` and no flag at any `targets` index. Excluded from the default suite.
- [x] T015 [P] [US2] Extend `tests/unit/pronunciation/test_drill_bank.py`: assert every `is_base` drill prompt has >1 word; every drill's `targets` indices are in range; each base contrast has ≥1 word follow-on.
- [x] T016 [US2] Update `src/speakloop/pronunciation/CLAUDE.md`: sentence-led bank, the flat-canonical rule, and the `live_pron` harness pointer — same commit.

---

## Phase 5: User Story 3 — Standalone `pronounce` mode (Priority: P3)

**Goal**: `speakloop pronounce` runs the loop outside a session with a RAM-only gate.

**Independent test**: with faked recorder/scorer/TTS, the loop runs; the gate ignores a configured
`local` engine (RAM only); declining provisioning exits clean; no report is written; the store tally
updates.

- [x] T017 [US3] Add `gate.assess_standalone_safety(*, min_free_mb, available_mb=None) -> SafetyDecision` to `src/speakloop/pronunciation/gate.py` (RAM-only, `engine="standalone"`, no engine penalty) and export it from `pronunciation/__init__.py` — per `contracts/standalone-gate.md`. Leave `assess_safety` (016) untouched.
- [x] T018 [P] [US3] Unit test `tests/unit/pronunciation/test_standalone_gate.py`: same low-RAM input → `assess_safety("local",…)` UNSAFE but `assess_standalone_safety(…)` follows RAM; high RAM → SAFE; psutil-absent → safe-cautious.
- [x] T019 [US3] Create `src/speakloop/cli/pronounce.py` with `run(...)` per `contracts/pronounce-command.md`: load config → `assess_standalone_safety` (+ freeze-warned override) → `ensure_models("A")` + `ensure_pronunciation_model` (decline → clean exit; NO ASR) → build scorer/bank/tts/play/record/key_reader → load store + derive `weak_contrasts` → user-paced loop via `select_drills` + `run_drill_item` (`q` quits) → closing summary + store `pronunciation_contrasts` update; NO markdown report. All heavy imports function-local.
- [x] T020 [US3] Register `@app.command("pronounce")` in `src/speakloop/cli/main.py` with a `--limit` option, delegating to `cli.pronounce.run` via a deferred (function-local) import so `--help` loads nothing.
- [x] T021 [P] [US3] Unit test `tests/unit/cli/test_pronounce_command.py`: standalone loop speaks before recording; RAM-only gate (a `local` `loop.yaml` does not block; low-RAM skips unless interactive override; model build never invoked when skipped); declining provisioning exits with no build; no report file is written; the store tally is updated.
- [x] T022 [US3] Update `src/speakloop/cli/CLAUDE.md` (the `pronounce` command + wiring) and `cli/doctor._pronunciation()` (a standalone-availability line + the new config keys) — same commit.

---

## Phase 6: User Story 4 — Practise the sounds you struggle with (Priority: P4)

**Goal**: bias selection toward weak contrasts in-run and across sessions (rebuildable store tally);
surface a "tricky sounds" summary; degrade to curated order with no history.

**Independent test**: a recorded weak contrast orders that contrast first; no history → curated order;
the tally round-trips + rebuilds from reports; a no-flags run adds nothing.

- [x] T023 [US4] Add an additive `pronunciation_contrasts: dict[str, list[list]]` section to `src/speakloop/store/model.py` (`Store` field + `to_dict`/`from_dict`; default `{}`); `STORE_VERSION` stays 1.
- [x] T024 [US4] Fold report `pronunciation_drills` → `pronunciation_contrasts` in `src/speakloop/store/rebuild.py` (append `[date, flagged_count]` per flagged contrast per session).
- [x] T025 [US4] Wire the tally: in `sessions/coordinator.py` write the flagged-contrast tally to the store after the analysis join (main thread, alongside the existing `patterns` write); in `cli/pronounce.py` read+write it; have both pass `weak_contrasts` (derived from the tally, most-weak first) into `select_drills`.
- [x] T026 [US4] Render the "tricky sounds" line: in `pronunciation/feedback.py` (additive, inside the report Pronunciation section) and in the standalone closing summary. Only when flags exist (byte-identical when absent).
- [x] T027 [P] [US4] Unit test `tests/unit/store/test_pronunciation_contrasts.py`: `Store` round-trips the section; `rebuild` folds it from a report fixture; an old store without the key loads to `{}`.
- [x] T028 [P] [US4] Unit test `tests/unit/pronunciation/test_select_drills.py`: weak contrasts ordered first (curated order within ties); empty history → curated order unchanged; `max_base` cap honoured.
- [x] T029 [US4] Update `src/speakloop/store/CLAUDE.md`: the new `pronunciation_contrasts` section + the rebuild caveat (standalone-only history lost on rebuild, matching the SRS `next_due` precedent) — same commit.

---

## Phase 7: User Story 5 — Docs (Priority: P5)

- [x] T030 [US5] Add/extend the README/quickstart pronunciation section: the trainer loop (hear-first, replay, bounded retry, sentences), the `speakloop pronounce` command, the new `loop.yaml` keys, and the unchanged 016 opt-in/offline/engine-memory gating.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T031 Update the root `CLAUDE.md`: SPECKIT block (active feature → 017, demote 016 to a one-liner), Commands (`pronounce` + the new flags/keys), and the module table (`cli/pronounce.py`, `pronunciation/drill_runner.py`). Keep ≤200 lines (gate `test_context_file_budget`).
- [x] T032 Update `doc/research_pronunciation.md` with the 017 "implementation decisions" (trainer loop, sentence canonical, standalone RAM-only gate, weak-sound store tally) — Constitution X.
- [x] T033 Extend `tests/integration/test_drills_additive_byte_identical.py`: a session that ran no drills stays byte-identical despite the new retry/tricky-sounds code paths; assert retry/tricky data is additive-only.
- [x] T034 Run and confirm green: `test_help_without_models`, `test_engine_import_isolation` (torch/transformers/kokoro_mlx still isolated; `pronounce` not imported at `--help`), `test_path_portability_audit`, `test_context_file_budget`, `test_analysis_equivalence`, `test_no_network_during_session`.
- [ ] T035 Run the full `uv run pytest`; record pass count vs the pre-feature baseline. Run an adversarial self-review (subagents) over the high-risk surfaces — the hear/retry loop, the standalone gate variant, offline preservation, the byte-identical-when-absent guarantee, single-live-display safety, and the bundled-phoneme harness — and fix confirmed findings.

---

## Dependencies & Execution Order

- **Setup (P1: T001–T002)** → no dependencies; do first.
- **Foundational (P2: T003–T007)** → depends on T002 (config); BLOCKS US1/US3/US4 (they call
  `run_drill_item`/`select_drills`). Complete before Phase 3+.
- **US1 (T008–T012)** → depends on Foundational. The MVP. Independently testable.
- **US2 (T013–T016)** → depends on Foundational; independent of US1 at runtime (bank data + harness).
  Can proceed in parallel with US1.
- **US3 (T017–T022)** → depends on Foundational (loop) + benefits from US2 (sentences). The gate
  variant (T017/T018) is independent and can start early.
- **US4 (T023–T029)** → depends on Foundational (`select_drills`); the store work (T023/T024/T027) is
  independent and can start early; T025/T026 integrate into US1 + US3.
- **US5 (T030)** → after the behaviour lands.
- **Polish (T031–T035)** → last; T031/T032 are the anti-rot context/doc updates (commit with the
  behaviour they describe where practical), T033–T035 are the verification gates + self-review.

## Parallel Opportunities

- T006, T007 (foundational tests) run in parallel once T003–T005 land.
- Across stories: T013/T014 (US2 bank+harness), T017/T018 (US3 gate), and T023/T024/T027 (US4 store)
  are independent files and can be built concurrently after Foundational.
- Test tasks marked [P] (T006, T007, T011, T012, T015, T018, T021, T027, T028) touch separate files.

## Implementation Strategy

1. **MVP = Setup + Foundational + US1** (T001–T012): a real hear → say → see → retry loop in the
   interview session, degrading to 016 everywhere TTS/interactivity is absent. Shippable on its own.
2. **+US2** (sentences + harness): the loop practises real sentences; the harness guards correctness.
3. **+US3** (standalone `pronounce`): pronunciation practice off the feedback wait.
4. **+US4** (weak-sound focus): the loop concentrates on the learner's actual weaknesses.
5. **+US5 + Polish**: docs, anti-rot context updates, full-suite gates, adversarial self-review.

Each phase ends green (`uv run pytest`) before the next begins; every behaviour-changing commit
updates its owning CLAUDE.md in the same commit (constitution v1.1.0).
