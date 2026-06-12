# pronunciation

## Purpose

Optional **read-aloud** pronunciation scoring (016): score a spoken rendering of a KNOWN
target word against its canonical phonemes and give calibrated, segment-level feedback.
Owns the acoustic-model wrapper, the GOP math, the engine/RAM safety gate, the bundled
drill bank, and the calibrated drill wording. Single responsibility (Principle IV).

## Public interface (`__init__.py`)

- `build_scorer() -> PronunciationScorer` — wav2vec2-backed scorer; lazy model load on
  first `score`. Imports the wrapper lazily so `import speakloop.pronunciation` loads no torch.
- `PronunciationScorer` (Protocol) — `score(wav, *, canonical, targets, tip, competitors,
  drill_id, text, contrast_id) -> DrillResult`. NEVER raises into the session: silent read →
  `not_captured`; failure → `error`.
- `DrillResult`, `PhoneFlag`, `PronunciationError` (`interface.py`).
- `load_drill_bank() -> DrillBank`; `Drill`, `Contrast`, `DrillBankError` (`drill_bank.py`).
- `assess_safety(engine, *, min_free_mb, available_mb=None) -> SafetyDecision` (`gate.py`).
- `render_drills_section(drills_dict) -> str | None`, `live_flag_summary(flags)` (`feedback.py`).

## The function-local engine-import rule (Principle V; root CLAUDE.md O1)

`wav2vec2_engine.py` is the ONLY file that imports `torch` / `transformers`, and ONLY inside
`_load()` / `_logits_to_logp()`. No other file in the module (and nothing on the CLI/`--help`
path) imports them. Guards: `tests/unit/asr/test_engine_import_isolation.py` (maps
`torch`,`transformers` → `pronunciation/wav2vec2_engine.py`), `tests/integration/
test_help_without_models.py` (their leak set includes `torch`,`transformers`).

## Model + scoring (research D3/D4)

- Model `facebook/wav2vec2-lv-60-espeak-cv-ft` (Apache-2.0, ~1.26 GB single `pytorch_model.bin`,
  emits IPA phonemes, vocab 392). Run on **CPU** (avoids MPS op gaps; MPS is a Future toggle).
- `gop.py` is **pure numpy** (no torch/k2/ctc_segmentation): CTC forced alignment (Viterbi over
  the blank-extended canonical sequence) + per-phone GOP + top competitor. Unit-tested with
  SYNTHETIC posteriors — no model needed.
- The CTC blank is the model's `<pad>` token (id 0).

## Offline + bundled phonemes (research D2 — load-bearing)

Canonical phonemes are **bundled** per drill in `drill_bank.yaml` (model symbol set, validated
vs the model `vocab.json`). The runtime does **no** grapheme-to-phoneme call — `g2p_en` was
rejected because it fetches NLTK data over the network on first use (breaks offline-first /
`test_no_network_during_session`). Author/re-validate canonical sequences against the model on a
real run (TTS the prompt → run the model → compare greedy decode); `g2p_en` may be used as an
offline authoring aid only (NOT shipped, NOT declared).

## Safety gate (`gate.py`, P3 — SC-001)

`assess_safety` decides whether loading the ~2–3 GB model is safe. **`engine == "local"` is
ALWAYS unsafe** (the local Qwen model dominates the budget). Cloud engine + available RAM ≥
`min_free_mb` → safe; below → unsafe (low memory); psutil absent → safe-cautious. It only
DECIDES; the CLI loads the model only on safe (or an explicit freeze-warned override). `psutil`
is imported function-local; stdlib can't report *available* RAM on darwin.

## Calibration (`feedback.py`, FR-009)

Lead with DETECTION ("the w sound sounded off"); show a phone DIAGNOSIS only as a hedged
SUGGESTION when `PhoneFlag.confident_diagnosis` (clear GOP + competitor margin). Never a verdict.

## Dependencies & consumers

- Third-party: `torch`,`transformers` (wav2vec2_engine only, function-local); `psutil`
  (gate only, function-local); `numpy`,`pyyaml`,`soundfile`,`scipy` (declared).
- Internal: `speakloop.installer` (model path/manifest). No other engine wrappers.
- Consumers (all function-local): `cli.practice` (gate + offer + build), `cli.doctor`
  (status section), `sessions.coordinator` (drill block), `feedback.report_builder` (section).

## File map

- `interface.py` — Protocol + `DrillResult`/`PhoneFlag` + `PronunciationError` (no engine import).
- `gop.py` — pure-numpy CTC forced alignment + GOP + competitor.
- `gate.py` — engine + live-RAM `assess_safety` (psutil function-local).
- `drill_bank.py` + `drill_bank.yaml` — bundled curated drills + bounded follow-on routing.
- `feedback.py` — calibrated Markdown/terminal wording.
- `wav2vec2_engine.py` — the ONLY torch/transformers importer; `build_scorer` + `Wav2Vec2Scorer`.

## Invariants & traps

- `score()` and the gate NEVER raise into the session; failures degrade (`error`/skip).
- No runtime g2p/NLTK/network (Constitution II); drill audio is scratch, discarded after scoring.
- CPU inference + `torch.no_grad()`; deterministic given the same audio + canonical.
- The model is NOT in any `PHASE_*_MODELS` list — fetched only via `installer.ensure_pronunciation_model`.

## Common modification patterns

- **Swap the acoustic model**: edit `wav2vec2_engine.py` (+ `manifest.WAV2VEC2_PRONUNCIATION`).
  Keep imports function-local; re-validate the bundled canonical phonemes vs the new vocab.
- **Add a drill/contrast**: edit `drill_bank.yaml` (validate symbols vs the model vocab).
- **Tune flag thresholds**: the `_*_THRESHOLD` constants in `wav2vec2_engine.py`.
- **Tune the gate**: `loop.yaml pronunciation_min_free_mb`; logic in `gate.py`.

## Pointers

- Root map: `../../../CLAUDE.md`. Spec/plan: `specs/016-pronunciation-drills/`.
- Research: `doc/research_pronunciation.md` + `specs/016-pronunciation-drills/research.md`.
- Concurrency with feedback: `src/speakloop/sessions/CLAUDE.md` (drill block runs while
  `_analyze` runs in a background thread). Test rules: `.claude/rules/testing.md`.
