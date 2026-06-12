# Contract: `pronunciation/` module public surface

The module is the single owner of read-aloud pronunciation scoring, the safety gate, the bundled
drill bank, and the calibrated drill-feedback wording. Heavy engine imports (`torch`, `transformers`)
are **function-local in `wav2vec2_engine.py` only** (Principle V); `pronunciation/__init__.py` and all
other files in the module import **no** engine package at module load, so `speakloop --help` and the
CLI import stay model-free.

## `pronunciation/__init__.py` exports

- `PronunciationScorer` (Protocol), `DrillResult`, `PhoneFlag`, `PronunciationError` — from `interface`.
- `load_drill_bank() -> DrillBank` — from `drill_bank`.
- `build_scorer() -> PronunciationScorer` — factory; constructs the wav2vec2-backed scorer (lazy
  model load on first `score`). Raises `PronunciationError` if the model dir is missing.
- `assess_safety(engine, *, min_free_mb, available_mb=None) -> SafetyDecision` — from `gate`.
- `render_drills_section(drills_dict) -> str | None` — from `feedback` (used by report_builder).

## `PronunciationScorer.score(...)`

```
score(wav_path: Path, *, canonical: list[str], target_indices: list[int], contrast) -> DrillResult
```

- Input: a 16 kHz mono WAV (the recorder's output), the drill's canonical phoneme sequence (model
  symbol set), the indices in `canonical` carrying the target contrast, and the `Contrast` record.
- Behavior: load audio → wav2vec2 logits → log-softmax `[T, vocab]` → CTC **forced alignment** of
  `canonical` (via `gop`) → per-phone GOP + top competitor → build `PhoneFlag`s (flag phones below the
  GOP threshold; always evaluate the `target_indices`). On empty/near-silent audio → `DrillResult(status="not_captured")`. On model/scoring failure → `DrillResult(status="error", detail=…)` (never raises into the session).
- Output: `DrillResult` (see data-model §2). Pure w.r.t. global state; safe to call repeatedly.
- **Determinism**: CPU inference; `torch.no_grad()`; no sampling. Same audio+canonical → same result.

## `gop.py` (pure numpy, NO heavy deps — unit-tested with synthetic posteriors)

```
forced_align(canonical_ids: list[int], logp: np.ndarray, blank_id: int) -> list[tuple[int,int]]
    # returns inclusive frame span [start,end] per canonical token via CTC Viterbi forced alignment
gop_scores(canonical_ids, spans, logp) -> list[float]               # mean log P(token) over its span
top_competitor(span, logp, blank_id, exclude_id) -> tuple[int,float]# argmax non-blank!=expected + margin
```

Contract: given a `[T, vocab]` log-posterior matrix where the canonical tokens dominate their regions,
`forced_align` returns monotonic non-overlapping spans covering the sequence, and `gop_scores` returns
high (near-0) values; planting a competitor mass at a target token lowers its GOP and makes
`top_competitor` return that competitor — this is exactly what the unit tests assert (no model needed).

## `gate.assess_safety(...)` → `SafetyDecision`

See `contracts/safety-gate.md`.

## `drill_bank` API

```
load_drill_bank() -> DrillBank
DrillBank.base_drills() -> list[Drill]                  # the session's base set (bounded)
DrillBank.next_drills(contrast_id, *, exclude_ids, max=2) -> list[Drill]   # follow-on minimal pairs
DrillBank.contrast(contrast_id) -> Contrast
```

`Drill`: `id, text, contrast_id, canonical: list[str], target_indices: list[int], minimal_pairs`.
`Contrast`: `id, expected, competitors, tip`.

## `feedback.render_drills_section(drills_dict) -> str | None`

Pure formatter (data-model §5). Detection-led, diagnosis hedged (FR-009). `None` when no items.

## Invariants

- No file in the module imports `torch`/`transformers` at module scope (guarded by
  `test_engine_import_isolation.py` + `test_help_without_models.py`).
- `score()` and `render_*` never raise into the coordinator — failures degrade to `error`/`None`.
- The drill bank is read-only; no runtime g2p/NLTK/network (Constitution II).
