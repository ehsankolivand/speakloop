# Implementation Plan: Pronunciation Drills

**Branch**: `016-pronunciation-drills` | **Date**: 2026-06-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/016-pronunciation-drills/spec.md`

## Summary

Add an optional, opt-in **read-aloud pronunciation-drill stage** that runs during the otherwise-idle
post-attempt feedback wait. After the 3 attempts + follow-ups, when drills are enabled *and* a
resource/engine **safety gate** permits, the coordinator runs the existing text feedback in a
**background thread** while a **user-paced read-aloud drill block** runs on the main thread; the
combined report (with a new additive **Pronunciation** section) is shown only after both finish.

Scoring is **read-aloud only** (known target text): a new `pronunciation/` module wraps a wav2vec2
CTC **phoneme** model (`facebook/wav2vec2-lv-60-espeak-cv-ft`, Apache-2.0) and computes per-phone
**Goodness-of-Pronunciation (GOP)** by **pure-numpy CTC forced alignment** against each drill's
**bundled canonical phoneme sequence** — no runtime grapheme-to-phoneme service, no NLTK, no network.
The heavy model is loaded only when the **engine-aware + live-RAM** gate says it is safe (typically a
cloud feedback engine with the local Qwen not resident); otherwise the drills are skipped with a
plain-language reason and an explicit, freeze-warned override. The model is fetched only on first
opt-in, through the **existing aria2 resilient downloader** (extended in place for a single-file,
non-safetensors model). Everything is additive: grammar/coaching, prompts, report `schema_version`,
and offline-by-default are unchanged.

## Technical Context

**Language/Version**: Python 3.12 (`>=3.12,<3.13`), `uv` only.

**Primary Dependencies (new/affected, all verified against PyPI/HF primary sources 2026-06-12)**:
- `transformers` (Apache-2.0) — load `Wav2Vec2ForCTC` + `Wav2Vec2Processor`. **Already resolved transitively** in `uv.lock` (5.8.1); we now import it directly, so declare it (`transformers>=4.34`) like `scipy`/`onnxruntime` are declared. Pin a floor only; do not force an upgrade.
- `torch` (BSD-3) — **already present** (2.8.0 via `torchaudio<2.9`). **Do NOT bump torch/torchaudio** (Trap 1). wav2vec2 inference runs on **CPU** (no MPS op-coverage risk; a single 5–20 s utterance scores in ~1–4 s).
- `psutil` (BSD-3-Clause, 7.2.2; ships macOS-arm64 wheel) — live available RAM via `virtual_memory().available`. New declared dep. Stdlib cannot report *available* (vs total) RAM on darwin (`SC_AVPHYS_PAGES` is unsupported), so psutil is the right, lightweight pick; the gate degrades gracefully if it is somehow unavailable.
- Model: `facebook/wav2vec2-lv-60-espeak-cv-ft` — Apache-2.0, **single `pytorch_model.bin` ≈ 1.26 GB, no safetensors / no shard index**, emits space-separated IPA phoneme tokens (vocab 392). Aux files: `config.json`, `preprocessor_config.json`, `vocab.json`, `tokenizer_config.json`, `special_tokens_map.json`.
- **Rejected** (with reasons, recorded in research.md): `g2p_en` (Apache-2.0 but fetches NLTK data over the network on first use → offline violation; replaced by bundled canonical phonemes), `ctc_segmentation` (Apache-2.0 but sdist-only Cython build against numpy-2 → install-fragility risk; replaced by ~80 lines of pure-numpy CTC alignment), `ctc-forced-aligner`/MahmoudAshraf (pulls `torchcodec`/Trap-1 + CC-BY-NC), `charsiu` model (undeclared license, git-only), `parselmouth`/`espeak`/`phonemizer` (GPL).

**Storage**: model under `~/.speakloop/models/<repo-slug>/` (existing `manifest.Model.local_path`); drill results in the session-report frontmatter (additive optional key) + a new Markdown body section; drill bank bundled in-package; drill audio is scratch and discarded after scoring.

**Testing**: `pytest`. Heavy model + mic are never touched in tests: the wav2vec2 wrapper is injected/faked, and the GOP+alignment math is unit-tested with **synthetic CTC posteriors** (no model). New tests for the gate, concurrent drill+feedback merge, aria2-fetch path, and the `--help`/import-isolation guards.

**Target Platform**: Apple Silicon, ~18 GB unified memory.

**Project Type**: Single-project offline CLI (Typer + Rich), 19 single-responsibility modules; this adds a 20th (`pronunciation/`).

**Performance Goals**: Per-drill scoring on CPU within a few seconds (user-paced; runs while the
user reads the next item). The drill block runs concurrently with feedback so it adds **0** wall-clock
to a cloud session's critical path in the common case.

**Constraints**: Offline after the one-time download; `speakloop --help` loads no engine/model
package; report `schema_version` stays 1; never load the model when unsafe (SC-001); byte-identical
report when no drills ran (SC-003); single resilient download path (FR-019); MIT-clean deps (no GPL).

**Scale/Scope**: ~3–4 base drills/session + ≤2 follow-on minimal-pair drills (bounded, FR-024);
a curated drill bank of a few dozen items.

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1. Constitution v1.1.0.*

| Principle / Constraint | Status | How this plan complies |
|---|---|---|
| I. English-only UI | ✅ | All drill prompts, tips, report text, warnings are English. |
| II. Offline-first | ✅ | After the one-time aria2 download, **zero** network: canonical phonemes are **bundled**; no g2p/NLTK runtime fetch; psutil/torch are local. `tests/integration/test_no_network_during_session.py` stays green. |
| III. Privacy by design | ✅ | Drill audio is local scratch, discarded after scoring; nothing uploaded. |
| IV. Modular (NON-NEGOTIABLE) | ✅ | New single-responsibility `pronunciation/` module with its own CLAUDE.md (≤200 lines). |
| V. Swappable engines | ✅ | wav2vec2 behind a `PronunciationScorer` wrapper; `torch`/`transformers` imported **function-local in exactly one file**; isolation guard extended. Swapping the model touches one file. |
| VI. Resumable downloads | ✅ | Reuses the aria2 resilient downloader (+ `snapshot_download(resume_download=True)` fallback). No bespoke path (FR-019). |
| VII. Apple Silicon primary | ✅ | CPU inference (robust on M-series); MPS is a documented Future. Footprint tuned for 18 GB. |
| VIII. Easy install / `--help` works | ✅ | Function-local imports → `--help` loads nothing new (guard extended with `torch`,`transformers`). **No build-from-source dep** (ctc_segmentation rejected for this reason); deps are wheels. |
| IX. Obsidian reports | ✅ | Additive optional frontmatter key + new body section; `schema_version` stays 1; no key made required. |
| X. Research in repo | ✅ | `doc/research_pronunciation.md` updated with the decisions + substitutions (already drafted; finalize in the same commit). |
| XI. AI-collaborator friendly | ✅ | Module CLAUDE.md keeps context loadable; owning context files updated in-commit (anti-rot). |
| XII. Iterative delivery | ✅ | MVP = P1 drill block + P3 gate; P2/P4/P5 layer on; every piece degrades gracefully (no model / no mic / scoring fail / unsafe → session still completes). |
| Constraints: Py3.12, uv, models under `~/.speakloop/models`, YAML config, CLI-only, no external services beyond HF download, MIT, public | ✅ | New `loop.yaml` keys (optional, silent default); model under models dir; no new service (psutil is local); all deps Apache-2.0/BSD/MIT — **no GPL**. |
| Dev guideline: context files rot unless same-commit updated | ✅ | Each behavior-changing commit updates its owning CLAUDE.md (`pronunciation/`, `sessions/`, `installer/`, `config/`, `feedback/`, `cli/`, root) + research doc. |
| Trap 1: don't bump `torchaudio` ≥2.9 / no k2 | ✅ | Keep torch/torchaudio ~2.8; rejected deps that pull `torchcodec`/k2. |
| Trap 2: module-level engine import breaks `--help` | ✅ | All heavy imports function-local; guards extended. |
| Trap 3: serial==concurrent byte-identical report | ✅ | `_analyze` is unchanged in output; backgrounding it doesn't change the bytes; pronunciation section is additive-when-present. |

**Result**: PASS. No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/016-pronunciation-drills/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions, substitutions, calibration, gate math
├── data-model.md        # Phase 1 — entities, frontmatter shape, drill-bank schema
├── quickstart.md        # Phase 1 — enable/disable, gate behavior, manual test
├── contracts/
│   ├── pronunciation-module.md   # PronunciationScorer + gate + drill-bank API
│   ├── safety-gate.md            # SAFE/UNSAFE decision contract
│   └── downloader-extension.md   # weight_files + META_FILES extension contract
└── checklists/requirements.md    # spec quality checklist (done)
```

### Source code (repository root)

```text
src/speakloop/pronunciation/            # NEW single-responsibility module (Principle IV)
├── __init__.py                         # public surface: scorer factory, gate, drill bank, errors
├── CLAUDE.md                           # module guide (≤200 lines)
├── interface.py                        # PronunciationScorer Protocol + DrillResult/PhoneFlag dataclasses + PronunciationError
├── wav2vec2_engine.py                  # ONLY file importing torch + transformers (function-local in _load())
├── gop.py                              # pure-numpy CTC forced alignment + GOP + competitor diagnosis (NO heavy deps)
├── gate.py                             # engine-aware + live-RAM SAFE/UNSAFE decision (psutil, function-local)
├── drill_bank.py                       # load + types for the bundled bank; next-drill routing for a contrast
├── drill_bank.yaml                     # bundled curated drills: text + canonical phones + target contrast + tip + minimal pairs
└── feedback.py                         # turn DrillResult(s) into calibrated, hedged report text (lead with detection)

src/speakloop/installer/
├── manifest.py                         # + WAV2VEC2_PRONUNCIATION model; + optional Model.weight_files field
├── downloader.py                       # + use model.weight_files when set; + preprocessor_config.json in META_FILES
└── __init__.py                         # + ensure_pronunciation_model(...) (reuses consent/download/validate)

src/speakloop/sessions/coordinator.py   # + _run_pronunciation_drills(); background-thread _analyze while drills run; assemble pronunciation section; _analyze(quiet=…)
src/speakloop/feedback/frontmatter.py   # + Session.pronunciation_drills additive optional key (schema_version stays 1)
src/speakloop/feedback/report_builder.py# + _pronunciation_drills_section() (rendered after interview-loop sections, before transcripts)
src/speakloop/config/loop_config.py     # + pronunciation_drills (auto|on|off) + pronunciation_min_free_mb keys (optional, silent defaults)
src/speakloop/cli/practice.py           # build drill capability once (gate+offer+provision+scorer); --drills/--no-drills; pass into run_session
src/speakloop/cli/doctor.py             # + Pronunciation drills section (model optional/never-FAIL; setting; gate estimate)
src/speakloop/cli/engine_status.py      # (optional) drills-availability helper reused by doctor/setup

# Context files updated in-commit (anti-rot): the new pronunciation/CLAUDE.md, plus
# sessions/, installer/, config/, feedback/, cli/ CLAUDE.md and the root CLAUDE.md SPECKIT block.

tests/
├── unit/pronunciation/test_gop.py                 # alignment + GOP + competitor on SYNTHETIC posteriors (no model)
├── unit/pronunciation/test_gate.py                # SAFE/UNSAFE matrix (engine × free-RAM), override, off
├── unit/pronunciation/test_drill_bank.py          # bank loads; canonical phones map to vocab; routing
├── unit/pronunciation/test_feedback_calibration.py# detection-led, diagnosis hedged (FR-009)
├── unit/installer/test_pronunciation_model.py      # weight_files used (not discover_shards); aria2 path; preprocessor_config.json fetched
├── integration/test_drills_concurrent_with_feedback.py # drills run while feedback runs; report waits for both; merged section
├── integration/test_drills_additive_byte_identical.py  # no drills → byte-identical report (complements analysis_equivalence)
└── (extend) tests/integration/test_help_without_models.py + tests/unit/asr/test_engine_import_isolation.py  # add torch, transformers
```

**Structure Decision**: One new module (`pronunciation/`) owns scoring + gate + drill bank + drill
feedback wording; the coordinator orchestrates the concurrency; the installer registers the model;
feedback/ renders it; cli/ wires the gate/offer/provisioning. This keeps each concern in exactly one
place (Principle IV/V) and confines the heavy `torch`/`transformers` imports to one wrapper file.

## Complexity Tracking

*No constitution violations — section intentionally empty.*
