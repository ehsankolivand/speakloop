# Data Model: Pronunciation Drills (016)

All structures are **additive**. The report `schema_version` stays **1**; every new field is optional
and emitted only when present (a no-drills session is byte-identical to a pre-feature report).

## 1. Bundled drill bank (`src/speakloop/pronunciation/drill_bank.yaml`)

Curated, shipped in-package, loaded via `Path(__file__).parent / "drill_bank.yaml"` (mirrors how
`feedback/openrouter_prompt_default.txt` is packaged). Read-only at runtime.

```yaml
# drill_bank.yaml
version: 1
contrasts:                         # the sound pairs the bank can exercise
  - id: "w_r"
    expected: "w"                  # IPA symbol present in the model vocab (vocab.json)
    competitors: ["ɹ", "r"]        # phones a confusion would produce
    tip: "Round your lips and don't curl your tongue back — 'wuh', not 'ruh'."
  - id: "v_w"
    expected: "v"
    competitors: ["w"]
    tip: "Touch your top teeth to your bottom lip for 'v'; lips don't round."
  # … ~10–20 common L2 contrasts (θ/s, ð/d/z, ɪ/iː, æ/ɛ, l/ɹ, …)

drills:
  - id: "wrapper-01"
    text: "The wrapper around the object adds a thin layer."
    contrast_id: "w_r"
    # canonical phoneme sequence in the MODEL's symbol set (authored + validated vs vocab.json, D2)
    canonical: ["ð","ə"," ","ɹ","æ","p","ɚ"," ", … ]
    # zero-based indices into `canonical` that carry the target contrast's expected phone
    target_indices: [3]            # (example) the onset of "wrapper"
    minimal_pairs: [["wrapper","rapper"], ["west","rest"], ["wing","ring"]]
  # … grouped so each contrast has ≥1 base drill + minimal pairs for follow-ons
```

**Validation (load time)**: every `expected`/`competitor`/`canonical` symbol must exist in the model
vocab when the model is present (a dev/test assertion uses a bundled tiny vocab fixture; production
load tolerates an absent model and only checks structural shape). `target_indices` in range. Each
drill references a known `contrast_id`.

**Routing (`drill_bank.next_drills(contrast_id, *, max=2)`)**: given a flagged contrast, return up to
`max` follow-on minimal-pair drills for that contrast (bounded, FR-024).

## 2. Runtime scoring types (`pronunciation/interface.py`)

```python
@dataclass(frozen=True)
class PhoneFlag:
    expected: str                  # canonical IPA phone that was off (detection)
    position_word: str             # the word it occurs in (for human-readable feedback)
    gop: float                     # mean log-posterior of the expected phone (lower = worse)
    competitor: str | None         # top competing phone over those frames (diagnosis SUGGESTION)
    competitor_margin: float       # how much the competitor beat the expected phone
    confident_diagnosis: bool      # True only when margins clear the hedge threshold (D8)

@dataclass(frozen=True)
class DrillResult:
    drill_id: str
    text: str
    contrast_id: str
    status: Literal["scored", "not_captured", "error"]
    flags: list[PhoneFlag]         # empty when nothing was off (good attempt)
    detail: str = ""               # e.g. error reason; never user-blaming on not_captured

class PronunciationScorer(Protocol):
    def score(self, wav_path: Path, *, canonical: list[str], target_indices: list[int],
              contrast) -> DrillResult: ...

class PronunciationError(Exception): ...   # single public error base
```

The wav2vec2 wrapper (`wav2vec2_engine.py`) implements `PronunciationScorer.score` by:
logits → log-softmax `[T, vocab]` → `gop.forced_align(canonical_ids, logp)` → per-phone GOP +
competitor → `PhoneFlag`s for phones below threshold (esp. at `target_indices`). All heavy imports
(`torch`, `transformers`) are **function-local in `_load()`** (Principle V).

## 3. Drill-block result (returned by the coordinator, stored in the report)

`_run_pronunciation_drills(...) -> dict | None` returns, when drills ran:

```python
{
  "engine_note": "offered because the local feedback model is not resident",
  "items": [
    {
      "drill_id": "wrapper-01",
      "text": "The wrapper around the object adds a thin layer.",
      "status": "scored",                      # scored | not_captured | error
      "flags": [
        {"expected": "w", "word": "wrapper", "competitor": "ɹ",
         "confident_diagnosis": false, "tip": "Round your lips …"}
      ],
      "is_follow_on": false,
      "contrast_id": "w_r",
    },
    # … base drills then any follow-on minimal-pair drills
  ],
  "summary": {"drills": 4, "with_flags": 2, "contrasts_practiced": ["w_r","θ_s"]},
}
```

`None` ⇒ no drills (off / declined / unsafe-skipped / no capability) ⇒ no frontmatter key, no section.

## 4. Report frontmatter (additive, `feedback/frontmatter.py`)

New optional field on `Session` (note: **distinct** from the existing `pronunciation_flags`, which is
the 010 ASR-mishearing list — different concept, different key):

```python
@dataclass
class Session:
    ...
    pronunciation_drills: dict | None = None   # the drill-block dict above; None ⇒ omitted
```

`dump()` emits `pronunciation_drills` only when truthy (like `warmup`); `parse()` reads it back as a
plain dict (forward/back-compatible; unknown to old readers). `schema_version` stays **1**. Free-text
(tips, sentence text) lives in the dict; nothing is made required.

## 5. Report body section (`feedback/report_builder.py`)

`_pronunciation_drills_section(session) -> str | None` — rendered **after** the interview-loop
sections and **before** the transcripts; returns `None` when `session.pronunciation_drills` is absent
(keeps no-drills reports byte-identical). Wording per D8/FR-009:

```markdown
## Pronunciation drills

_Read-aloud practice. Detection (a sound was off) is reliable; any specific "heard as …"
guess is a suggestion, not a verdict._

- **The wrapper around the object adds a thin layer.**
  - The **w** in *wrapper* sounded off. _(suggestion: it may have come out closer to **r**)_
  - Tip: Round your lips and don't curl your tongue back — 'wuh', not 'ruh'.
- **west / rest** (follow-up) — clear ✓
- _(silent — not captured) The thin theory …_  ← honest, never a "fail"
```

Detection is always stated; the parenthetical diagnosis appears only when `confident_diagnosis` is
true, and always hedged.

## 6. Config keys (`config/loop_config.py`, additive optional)

| Key | Default | Validation |
|---|---|---|
| `pronunciation_drills` | `"auto"` | must be in `("auto","on","off")`, else default |
| `pronunciation_min_free_mb` | `4500` | `max(0, int)`, else default |

Both are read-only-with-default (hand-edited in `loop.yaml`, like `daily_capacity`); no writer is
added. `doctor`/`setup` may display the current value.

## 7. Installer model registration (`installer/manifest.py`)

```python
@dataclass(frozen=True)
class Model:
    name: str
    hf_repo_id: str
    expected_size_bytes: int
    required_for_phase: Phase
    weight_files: tuple[str, ...] | None = None   # NEW: explicit non-safetensors weight list

WAV2VEC2_PRONUNCIATION = Model(
    name="wav2vec2-phoneme-en",
    hf_repo_id="facebook/wav2vec2-lv-60-espeak-cv-ft",
    expected_size_bytes=1_262_000_000,            # ~1.26 GB single pytorch_model.bin (±25% tol)
    required_for_phase="C",                       # phase label only; NOT in any PHASE_*_MODELS list
    weight_files=("pytorch_model.bin",),
)
```

It is **not** added to `PHASE_A/B/C_MODELS`, so no phase auto-fetches it; only
`ensure_pronunciation_model()` references it. `required_for_phase` is set to a valid literal purely to
satisfy the dataclass; it is never used for phase provisioning.

## State / lifecycle

```
attempts done → (CLI pre-decided) drills permitted?
  ├─ no  → _analyze() inline (today's path, byte-identical)
  └─ yes → start _analyze() in bg thread (quiet)  ┐
           run drill block (user-paced) on main   ├─ join → assemble report (+ pronunciation section)
           drill audio scored then discarded      ┘
```
