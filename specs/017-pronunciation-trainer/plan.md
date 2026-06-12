# Implementation Plan: Pronunciation Trainer (hear → say → see → retry)

**Branch**: `017-pronunciation-trainer` | **Date**: 2026-06-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/017-pronunciation-trainer/spec.md`

**Base**: branches off `016-pronunciation-drills` (016 is **not yet merged to main**; see Notes). All
of 016's `pronunciation/` module, the safety gate, the bundled-phoneme approach, and the aria2
download flow are reused.

## Summary

Turn 016's read-aloud drill block into a real **hear → say → see → retry** trainer and make it usable
on its own:

1. **Hear-first + bounded retry (P1)** — before each drill the existing **Kokoro TTS** speaks the
   target so the learner hears it first (replayable on demand with `r`); when a sound is flagged the
   loop does a **bounded automatic retry** on the same item (default 1) and reports whether it
   improved, in calibrated/non-blaming language. Both degrade to the exact 016 behaviour when no TTS
   or no interactive terminal is present.
2. **Sentence-level drills (P2)** — the bundled bank gains natural **sentences** as base drills (with
   bundled, offline canonical phonemes); word minimal-pairs remain bounded follow-ons.
3. **Standalone `pronounce` mode (P3)** — a new thin CLI command runs the same loop outside an
   interview session, user-paced, using a **RAM-only** gate variant (no feedback engine resident);
   it provisions only TTS + the pronunciation model through the existing consent/download flow.
4. **Weak-sound focus (P4)** — selection biases toward flagged contrasts in-run, and a lightweight
   per-contrast tally in the **derived store** biases future runs (graceful fallback to curated order
   with no history) and feeds a short "tricky sounds" summary.

The per-drill loop is factored into a **pure, UI-agnostic** `pronunciation/drill_runner.py` shared by
the interview drill block (sessions) and the standalone command (cli), with recording UI + TTS +
scorer injected. Everything is additive: grammar/coaching, report `schema_version` (1), `STORE_VERSION`
(1), offline-by-default, and the byte-identical no-drills report are all unchanged. The required
**TTS-through-scorer correctness harness** ships as a self-skipping live test.

## Technical Context

**Language/Version**: Python 3.12 (`>=3.12,<3.13`), `uv` only.

**Primary Dependencies (all already present — no new third-party deps)**:
- `transformers` + `torch` (CPU) — the 016 wav2vec2 scorer, unchanged; imports stay function-local in
  `pronunciation/wav2vec2_engine.py`.
- `kokoro-mlx` (the existing TTS) — used for hear-first; imported function-local in `tts/kokoro_engine.py`.
- `psutil` — live RAM for the gate (016); reused by the new standalone gate variant (function-local).
- `numpy`, `pyyaml`, `soundfile`, `scipy`, `sounddevice`, `rich`, `typer` — all already declared.
- **No `torchaudio` bump, no `k2`, no `g2p_en`/NLTK at runtime** (Traps 1; offline-first preserved).

**Storage**: drill results in the session-report frontmatter (the 016 `pronunciation_drills` dict,
extended additively with per-item retry outcomes + a tricky-sounds summary); a new optional
`pronunciation_contrasts` section in the **derived store** (`~/.speakloop/store.json`, rebuildable,
`STORE_VERSION` stays 1); the bundled drill bank in-package; drill + TTS audio are scratch/cache.

**Testing**: `pytest`. Heavy model + mic + TTS never touched in the default suite — the scorer is
faked, `record_fn` injected, `tts_engine`/`play_fn` injected or `None`, the gate's RAM reading
injected. New default-suite tests cover hear-first ordering, bounded retry, the standalone loop + its
RAM-only gate, weak-sound selection, and the byte-identical guarantee. The TTS-through-scorer
correctness harness is a **self-skipping live test** (`live_pron` marker) excluded from the default
suite.

**Target Platform**: Apple Silicon, ~18 GB unified memory (CPU inference for the scorer; MPS deferred).

**Project Type**: Single-project offline CLI (Typer + Rich), 20 modules; this adds **no new module
dir** — new files land in existing modules (`pronunciation/drill_runner.py`, `cli/pronounce.py`).

**Performance Goals**: Hear-first synth reuses the TTS clip cache (a repeated target is instant). The
interview drill block stays concurrent with feedback (016), so it adds **0** wall-clock to the cloud
critical path in the common case; bounded retries keep it bounded.

**Constraints**: offline after the one-time download; `--help` loads no engine/model package;
report `schema_version` = 1 and `STORE_VERSION` = 1; byte-identical report when no drills ran;
single resilient download path; the standalone gate is a distinct variant (the 016 interview rule is
unchanged); CPU-only; English-only; YAML-only config.

**Scale/Scope**: interview block = ≤4 base drills + ≤2 follow-ons + ≤`pronunciation_retries` retries
each (bounded). Standalone = user-paced, ends on quit. Bank = a few dozen sentences + word follow-ons
across the 016 contrasts.

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1. Constitution v1.1.0.*

| Principle / Constraint | Status | How this plan complies |
|---|---|---|
| I. English-only UI | ✅ | All hear-first/retry/standalone prompts, summaries, tips are English. |
| II. Offline-first | ✅ | Hear-first uses the **local** Kokoro TTS; scoring + canonical phonemes are local/bundled; the weak-sound tally is local JSON. **Zero** runtime network. `test_no_network_during_session.py` stays green; a standalone-network guard is added. |
| III. Privacy by design | ✅ | Drill audio is local scratch, discarded after scoring; TTS clips are the existing local cache; the tally holds only contrast ids + counts. Nothing uploaded. |
| IV. Modular (NON-NEGOTIABLE) | ✅ | No new module dir. New `pronunciation/drill_runner.py` (pure loop logic, UI-agnostic) + `cli/pronounce.py` (thin command) live in existing modules; their CLAUDE.md files are updated in-commit (each stays ≤200 lines). |
| V. Swappable engines | ✅ | `torch`/`transformers` stay function-local in `wav2vec2_engine.py`; the TTS engine stays function-local in `tts/`; `pronounce.py` imports both function-local. `drill_runner.py` imports **no** engine package (scorer/tts injected, duck-typed). Isolation guards unchanged + still pass. |
| VI. Resumable downloads | ✅ | Standalone provisioning reuses `ensure_models("A")` + `ensure_pronunciation_model` (aria2 + snapshot fallback, consent + size disclosure). No bespoke path. |
| VII. Apple Silicon primary | ✅ | CPU scorer inference (016); Kokoro is the existing MLX TTS. Footprint unchanged; MPS still a Future. |
| VIII. Easy install / `--help` works | ✅ | `pronounce_cmd` defers all heavy imports to its body (like `practice_cmd`); `--help` imports neither `cli/pronounce.py` nor any engine. Guard `test_help_without_models.py` extended/asserted. No build-from-source dep added. |
| IX. Obsidian reports | ✅ | Retry outcomes + tricky-sounds nest inside the existing additive `pronunciation_drills` dict; `schema_version` stays 1; no key made required; no-drills report byte-identical. Standalone writes **no** report. |
| X. Research in repo | ✅ | `doc/research_pronunciation.md` updated with the trainer-loop, sentence-canonical, standalone-gate, and weak-sound decisions (in-commit). |
| XI. AI-collaborator friendly | ✅ | Pure `drill_runner.py` is unit-testable in isolation; owning CLAUDE.md files updated in-commit (anti-rot). |
| XII. Iterative delivery | ✅ | MVP = P1 loop (degrades to 016 everywhere TTS/interactivity is absent). P2/P3/P4/P5 layer on; every piece degrades gracefully (no TTS → no hear-first; no history → curated order; unsafe → skip). |
| Constraints: Py3.12, uv, models dir, YAML config, CLI-only, MIT, public | ✅ | New keys are optional `loop.yaml` keys (silent defaults); no new model/service; no new third-party dep; CLI-only. |
| Dev guideline: context files rot unless same-commit updated | ✅ | Each behavior-changing commit updates its owning CLAUDE.md (`pronunciation/`, `sessions/`, `cli/`, `config/`, `store/`, `feedback/`, root) + research doc. |
| Trap 1: no `torchaudio` ≥2.9 / no k2 | ✅ | No torch/torchaudio change; no k2; no new build-from-source dep. |
| Trap 2: module-level engine import breaks `--help` | ✅ | All heavy imports function-local; `pronounce.py` only imported inside its command body. |
| Trap 3: serial==concurrent byte-identical report | ✅ | The interview drill block still runs concurrently with a background `_analyze`; retry/tricky-sounds are additive-when-present; the single store mutation stays on the main thread after join. Gate `test_analysis_equivalence.py` + `test_drills_additive_byte_identical.py` hold. |

**Result**: PASS. No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/017-pronunciation-trainer/
├── plan.md              # This file
├── research.md          # Phase 0 — trainer-loop, sentence-canonical, standalone-gate, weak-sound decisions
├── data-model.md        # Phase 1 — extended drill dict, store section, config keys, gate variant
├── quickstart.md        # Phase 1 — try the loop + `pronounce`; manual test
├── contracts/
│   ├── drill-runner.md       # run_drill_item + select_drills pure-loop contract
│   ├── standalone-gate.md    # assess_standalone_safety (RAM-only) contract
│   └── pronounce-command.md  # `speakloop pronounce` CLI contract
└── checklists/requirements.md  # spec quality checklist (done)
```

### Source code (repository root)

```text
src/speakloop/pronunciation/
├── drill_runner.py        # NEW: pure, UI-agnostic per-drill loop (hear→say→see→retry) + select_drills
│                          #      (weak-sound ordering). Injected speak/record/scorer/key_reader/console.
│                          #      Imports NO engine package, NO sessions/tts/audio.
├── gate.py                # + assess_standalone_safety(*, min_free_mb, available_mb=None) (RAM-only variant)
├── feedback.py            # + retry-outcome + "tricky sounds" wording (calibrated, additive)
├── drill_bank.yaml        # + sentence base drills (bundled canonical phonemes); words → follow-ons
├── drill_bank.py          # + Drill.is_sentence helper (optional); select-by-weak-contrast support
└── __init__.py            # + export run_drill_item, select_drills, assess_standalone_safety

src/speakloop/sessions/coordinator.py   # _run_pronunciation_drills → build speak/record, call run_drill_item;
                                        #   thread tts_engine/play_fn in; fold flagged contrasts into store
src/speakloop/cli/pronounce.py          # NEW thin command: gate(RAM-only) → provision → loop → summary + store
src/speakloop/cli/main.py               # + @app.command("pronounce") (deferred import in the body)
src/speakloop/cli/practice.py           # pass tts_engine/play_fn into the drill bundle path (already injected)
src/speakloop/cli/doctor.py             # _pronunciation(): note standalone availability + new config keys
src/speakloop/config/loop_config.py     # + pronunciation_tts_playback (bool, True) + pronunciation_retries (int, 1)
src/speakloop/store/model.py            # + pronunciation_contrasts section (additive; STORE_VERSION stays 1)
src/speakloop/store/rebuild.py          # + fold report pronunciation_drills → pronunciation_contrasts
src/speakloop/feedback/report_builder.py# (unchanged entry; renders via pronunciation.feedback as today)

# Context files updated in-commit (anti-rot): pronunciation/, sessions/, cli/, config/, store/,
# feedback/ CLAUDE.md + the root CLAUDE.md (Commands + SPECKIT block) + doc/research_pronunciation.md.

tests/
├── unit/pronunciation/test_drill_runner.py        # hear-first ordering; bounded retry; improvement; degrade
├── unit/pronunciation/test_select_drills.py        # weak-sound ordering; no-history → curated order
├── unit/pronunciation/test_standalone_gate.py      # RAM-only: local-engine config does NOT block; low-mem unsafe
├── unit/pronunciation/test_feedback_retry_wording.py # retry/tricky-sounds calibrated + additive
├── unit/cli/test_pronounce_command.py              # standalone loop runs; RAM-only gate; declines clean; no report
├── unit/store/test_pronunciation_contrasts.py      # store round-trip + rebuild fold + no-history default
├── integration/test_drill_hear_first_and_retry.py  # interview block speaks before recording + bounded retry
├── integration/test_drills_additive_byte_identical.py # (extend) retry/tricky-sounds keep no-drills byte-identical
└── live_pron_test.py                               # LIVE (self-skipping): every bundled drill TTS→scorer scores clean
```

**Structure Decision**: The shareable per-drill loop becomes a **pure** `pronunciation/drill_runner.py`
(no UI/engine imports; speak/record/scorer injected), so both the interview block (sessions, with the
countdown/REC UI + concurrent feedback) and the standalone command (cli) reuse identical loop logic
while the recording UI stays in sessions and TTS stays in tts/. This honours "pronunciation/ owns the
loop logic" without creating a `pronunciation → sessions/tts/audio` cycle, and keeps every concern in
exactly one place (Principle IV/V).

## Complexity Tracking

*No constitution violations — section intentionally empty.*

## Notes

- **Base-branch / merge order**: 016 is not on `main` yet. This feature branches off
  `016-pronunciation-drills`. Merge order for integration: **016 → main, then 017 → main** (or merge
  016 then rebase 017 onto main). Called out again in the handoff.
