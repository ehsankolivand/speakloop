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
  speak, record, key_reader, console, scratch_dir, retries=1, tts_on=True, is_follow_on=False,
  teach_speak=None)` → item dict (hear-first + replay-on-demand + per-sound TEACHING beat +
  bounded retry); `run_drill_block(..., teach_speak=None)`; `select_drills(bank, *,
  weak_contrasts, max_base)` (weak-sound ordering, curated fallback); `build_block_result(items,
  *, bank, engine_note)` (the block dict + summary); `contrast_label`, `flagged_contrast_counts`;
  `DrillQuit` (learner pressed `q`). Injects speak/record/scorer/`teach_speak` — imports NO engine
  package and NO `sessions`/`tts`/`audio` (no cycle; unit-tested with fakes).
  - **P2 teaching beat (`_teach_sound`)**: on a flagged sound, BEFORE the retry it shows the curated
    respelling (`Drill.say_like`) + replays JUST the flagged word(s) in isolation via the slower
    `teach_speak` (falls back to `speak`). Kokoro has no phoneme-stress control → isolation + a
    slower rendering + the respelling is the documented approximation. The respelling is also shown
    with the drill at start. Interactive-only (gated with the retry), so piped runs stay 016-identical.
  - **P0 failure observability (`_score_once` → `(status, flags, detail)`)**: the score path never
    raises into the session, so the REAL reason was being flattened to a vague "could not score".
    `_score_once` now captures `DrillResult.detail` (model/scoring failure) OR the record/scorer
    exception text (mic failure), logs it at DEBUG (`logging.getLogger("speakloop.pronunciation.drill")`),
    and `_print_outcome` shows an ACTIONABLE, cause-distinguishing message (mic vs model). `SPEAKLOOP_DEBUG`
    (set by `pronounce --debug`) surfaces the raw `detail` inline; the report frontmatter is unchanged
    (detail is runtime-only, not persisted → no-drills report stays byte-identical). A retry that hits
    this failure is recorded as its OWN retry `outcome` `"error"` (never `"still_off"`): the actionable
    reason is printed once, no contradictory "still a little off" line is shown live, and `feedback._retry_line`
    returns `None` so the report claims no verdict for a retry that was never scored.

## The function-local engine-import rule (Principle V; root CLAUDE.md O1)

`wav2vec2_engine.py` is the ONLY file that imports `torch` / `transformers`, and ONLY inside
`_load()` / `_logits_to_logp()`. No other file in the module (and nothing on the CLI/`--help`
path) imports them. Guards: `tests/unit/asr/test_engine_import_isolation.py` (maps
`torch`,`transformers` → `pronunciation/wav2vec2_engine.py`), `tests/integration/
test_help_without_models.py` (their leak set includes `torch`,`transformers`).

## Model + scoring (research D3/D4)

- Model `facebook/wav2vec2-lv-60-espeak-cv-ft` (Apache-2.0, ~1.26 GB single `pytorch_model.bin`,
  emits IPA phonemes, vocab 392). Run on **CPU** (avoids MPS op gaps; MPS is a Future toggle).
- **espeak-free load (P0 — load-bearing)**: `_load()` builds ONLY a `Wav2Vec2FeatureExtractor`
  (+ the CTC model) and reads `vocab.json` DIRECTLY for `_sym2id` (`_read_vocab`). It must NOT build
  a `Wav2Vec2Processor` / `Wav2Vec2PhonemeCTCTokenizer`: that tokenizer's `__init__` eagerly inits
  the **espeak phonemizer** (text→phoneme), which the scorer never uses (bundled canonical phonemes)
  and which crashes the whole load with "espeak not installed on your system" when system espeak is
  absent/fragile — surfacing as EVERY drill "could not score this one" with NO "Loading weights" line
  (the processor loads before the model). Guarded by `tests/unit/pronunciation/test_scorer_thresholds.py`.
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
when the model/TTS are absent and is excluded from the default suite. **It is the calibration
oracle** and guards BOTH directions on real audio: over-flagging (clean drill → no flag) AND
under-flagging (IMP-024 — a deliberate minimal-pair substitution like `rest`/`doze`/`sin` scored
against the target word's canonical MUST flag), so a loosened `_COMPETITOR_FLAG_MARGIN` can't drift
into silently passing real errors. Drills whose target phone Kokoro renders as the wrong phone were DROPPED (`thick`→/s/,
`ship`/`fish`/`big`→/ɛ/, `they` borderline) and replaced with validated-clean words (`three`,
`sit`/`kit`/`bit`, `those`); the base sentences lead with a clean-scoring word (`Thin and thick.`,
`Sit in the seat.`). Each drill carries a curated `say_like` English respelling (P2; bundled, never
runtime-derived) shown with the drill and in the teaching beat.

## Safety gate (`gate.py`, P3 — SC-001)

`assess_safety` (interview) decides whether loading the ~2–3 GB model is safe. **`engine ==
"local"` is ALWAYS unsafe** (the local Qwen model dominates the budget). Cloud engine + available
RAM ≥ `min_free_mb` → safe; below → unsafe (low memory); psutil absent → safe-cautious. **017**:
`assess_standalone_safety` is the `speakloop pronounce` variant — **RAM-only, no engine penalty**
(no feedback model is resident in standalone mode), so a configured `local` engine does NOT block
it. The 016 interview rule is unchanged; this is a distinct function, not a weakening. Both only
DECIDE; the CLI loads the model only on safe (or an explicit freeze-warned override). `psutil` is
imported function-local; stdlib can't report *available* RAM on darwin.

## Calibration (`feedback.py`, FR-009 + thresholds in `wav2vec2_engine.py`)

Lead with DETECTION ("the w sound sounded off"); show a phone DIAGNOSIS only as a hedged
SUGGESTION when `PhoneFlag.confident_diagnosis` (clear GOP + competitor margin). Never a verdict.

**Flag thresholds** (`wav2vec2_engine.py`, calibrated against the live harness, NOT first-pass):
`_GOP_FLAG_THRESHOLD = -2.0`, `_COMPETITOR_FLAG_MARGIN = 1.5` (raised from 0.5). Live oracle data:
a clean TTS rendering of the target scores GOP ≳ -0.9 with the competitor LOSING (margin < 0); a
deliberate substitution scores GOP ≲ -2.4 with the competitor winning by margin ≳ +2.0. GOP alone
separates the two; the competitor margin is a corroborating signal set in the gap (1.5) so an
accented-but-acceptable sound is NOT over-flagged (0.5 over-flagged /w/ — the learner's symptom).

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
- `drill_runner.py` (017) — pure hear→say→see→retry loop + `_teach_sound` (P2 teaching beat) +
  failure-detail surfacing (`_score_once`→`(status,flags,detail)`, `SPEAKLOOP_DEBUG`) + `select_drills`
  + `build_block_result` + `DrillQuit`; injects speak/record/scorer/`teach_speak` (no engine/sessions/tts/audio).
- `drill_bank.py` + `drill_bank.yaml` — bundled sentence base drills + word follow-ons + routing +
  curated `Drill.say_like` English respellings (P2).
- `feedback.py` — calibrated Markdown/terminal wording (+ 017 retry/tricky-sounds lines).
- `wav2vec2_engine.py` — the ONLY torch/transformers importer; `build_scorer` + `Wav2Vec2Scorer`
  (espeak-free load: `Wav2Vec2FeatureExtractor` + `_read_vocab(vocab.json)`, NOT a processor).

## Invariants & traps

- `score()` and the gate NEVER raise into the session; failures degrade (`error`/skip) — but the
  REAL reason is captured into `detail` + logged + surfaced under `SPEAKLOOP_DEBUG` (never silently lost).
- An out-of-vocab TARGET phone → `error` (detail names the phone), NOT a false `scored`/"clear ✓":
  if NO target survived the vocab map, the model never evaluated the sound being taught (IMP-007).
  The `not canon_ids` guard (whole canonical unknown) still fires first.
- No runtime g2p/NLTK/network/**espeak** (Constitution II); the load reads `vocab.json` directly and
  must stay processor-free. Drill audio is scratch, discarded after scoring.
- CPU inference + `torch.no_grad()`; deterministic given the same audio + canonical.
- The model is NOT in any `PHASE_*_MODELS` list — fetched only via `installer.ensure_pronunciation_model`.

## Common modification patterns

- **Swap the acoustic model**: edit `wav2vec2_engine.py` (+ `manifest.WAV2VEC2_PRONUNCIATION`).
  Keep imports function-local + the load espeak-free (feature extractor + `vocab.json`, no processor);
  re-validate the bundled canonical phonemes + thresholds vs the new vocab on the live harness.
- **Add a drill/contrast**: edit `drill_bank.yaml` (validate symbols vs the model vocab; add a
  `say_like` respelling; run `-m live_pron` — a drill that false-flags its own clean TTS is rejected).
- **Tune flag thresholds**: the `_*_THRESHOLD`/`_*_MARGIN` constants in `wav2vec2_engine.py` (use the
  live harness as the clean-vs-substitution oracle).
- **Tune the gate**: `loop.yaml pronunciation_min_free_mb`; logic in `gate.py`.

## Pointers

- Root map: `../../../CLAUDE.md`. Spec/plan: `specs/016-pronunciation-drills/`.
- Research: `doc/research_pronunciation.md` + `specs/016-pronunciation-drills/research.md`.
- Concurrency with feedback: `src/speakloop/sessions/CLAUDE.md` (drill block runs while
  `_analyze` runs in a background thread). Test rules: `.claude/rules/testing.md`.
