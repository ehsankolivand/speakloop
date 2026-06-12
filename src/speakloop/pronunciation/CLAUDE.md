# pronunciation

## Purpose

Optional **read-aloud** pronunciation scoring + the **hear → say → see → retry** trainer loop
(016 + 017): score a spoken rendering of a KNOWN target (sentence or word) against its canonical
phonemes and give calibrated, segment-level feedback. Owns the acoustic-model wrapper, the GOP
math, the engine/RAM safety gate (interview + standalone variants), the bundled drill bank, the
pure per-drill loop, and the calibrated drill wording. Single responsibility (Principle IV).

## Public interface (`__init__.py`)

- `build_scorer() -> PronunciationScorer` — wav2vec2-backed scorer; lazy model load on
  first `score`. Imports the wrapper lazily so `import speakloop.pronunciation` loads no torch.
- `PronunciationScorer` (Protocol) — `score(wav, *, canonical, targets, tip, competitors,
  drill_id, text, contrast_id) -> DrillResult`. NEVER raises into the session: silent read →
  `not_captured`; failure → `error`.
- `DrillResult`, `PhoneFlag`, `PronunciationError` (`interface.py`).
- `load_drill_bank() -> DrillBank`; `Drill`, `Contrast`, `DrillBankError` (`drill_bank.py`).
- `assess_safety(engine, *, min_free_mb, available_mb=None) -> SafetyDecision` (`gate.py`, 016
  interview gate) **and** `assess_standalone_safety(*, min_free_mb, available_mb=None)` (`gate.py`,
  017 RAM-only variant — no engine penalty).
- `render_drills_section(drills_dict) -> str | None`, `live_flag_summary(flags)` (`feedback.py`).
- **017 loop (`drill_runner.py`, pure / UI-agnostic):** `run_drill_item(drill, *, contrast, scorer,
  speak, record, key_reader, console, scratch_dir, retries=1, tts_on=True, is_follow_on=False)`
  → item dict (hear-first + replay-on-demand + bounded retry); `select_drills(bank, *,
  weak_contrasts, max_base)` (weak-sound ordering, curated fallback); `build_block_result(items,
  *, bank, engine_note)` (the block dict + summary); `contrast_label`, `flagged_contrast_counts`;
  `DrillQuit` (learner pressed `q`). Injects speak/record/scorer — imports NO engine package and
  NO `sessions`/`tts`/`audio` (no cycle; unit-tested with fakes).

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

**017 — sentence bank**: base drills are SENTENCES; the 016 minimal-pair WORDS are `is_base: false`
follow-ons. A sentence's `canonical` is the FLAT CONCATENATION of its words' phonemes with **no
word-separator token** (CTC blanks already separate canonical tokens). The target contrast sits at
an unambiguous, usually sentence-initial position (`canonical[target.index] == contrast.expected`,
enforced by `test_drill_bank.py`). The authoritative pre-ship validation is the **live harness**
`tests/live_pron_test.py` (`uv run pytest -m live_pron`): it TTS-renders every drill, scores it, and
asserts NO flag on a clean rendering — a flag means the canonical/target is wrong. It self-skips
when the model/TTS are absent and is excluded from the default suite.

## Safety gate (`gate.py`, P3 — SC-001)

`assess_safety` (interview) decides whether loading the ~2–3 GB model is safe. **`engine ==
"local"` is ALWAYS unsafe** (the local Qwen model dominates the budget). Cloud engine + available
RAM ≥ `min_free_mb` → safe; below → unsafe (low memory); psutil absent → safe-cautious. **017**:
`assess_standalone_safety` is the `speakloop pronounce` variant — **RAM-only, no engine penalty**
(no feedback model is resident in standalone mode), so a configured `local` engine does NOT block
it. The 016 interview rule is unchanged; this is a distinct function, not a weakening. Both only
DECIDE; the CLI loads the model only on safe (or an explicit freeze-warned override). `psutil` is
imported function-local; stdlib can't report *available* RAM on darwin.

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
- `gate.py` — `assess_safety` (016 interview) + `assess_standalone_safety` (017 RAM-only); psutil
  function-local.
- `drill_runner.py` (017) — pure hear→say→see→retry loop + `select_drills` + `build_block_result`
  + `DrillQuit`; injects speak/record/scorer (no engine/sessions/tts/audio import).
- `drill_bank.py` + `drill_bank.yaml` — bundled sentence base drills + word follow-ons + routing.
- `feedback.py` — calibrated Markdown/terminal wording (+ 017 retry/tricky-sounds lines).
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
