# Data Model: Pronunciation Trainer (017)

All structures are **additive** on top of 016. The report `schema_version` stays **1** and the
`STORE_VERSION` stays **1**; every new field is optional and emitted only when present. A no-drills
session is byte-identical to a pre-feature report.

## 1. Drill bank (`src/speakloop/pronunciation/drill_bank.yaml`) — sentence-led

The 016 schema is unchanged; the bank gains **sentence** base drills and keeps word minimal-pairs as
follow-ons. `canonical` is the **flat concatenation** of per-word phonemes in the model symbol set
(no word-separator token — CTC blanks separate tokens, research D3). `targets` indexes the contrast
phone within that flat list.

```yaml
contrasts:                         # (016, unchanged shape) sound pairs the bank exercises
  - id: "v_w"
    expected: "v"
    competitors: ["w"]
    tip: "For 'v', press your top teeth on your bottom lip and add voice. Lips don't round."

drills:
  # NEW: sentence base drill (is_base: true). target indexes the contrast phone in the flat sequence.
  - id: "vw-sentence-01"
    contrast_id: "v_w"
    prompt: "We verify every value."
    canonical: ["w","iː","v","ɛ","ɹ","ɪ","f","aɪ","ɛ","v","ɹ","i","v","æ","l","j","uː"]
    targets: [{index: 2, word: "verify"}]   # the word-initial /v/ of "verify"
    is_base: true
  # 016 word drills remain as follow-ons (is_base omitted/false) for the same contrast.
  - id: "vest"
    contrast_id: "v_w"
    prompt: "vest"
    canonical: ["v","ɛ","s","t"]
    targets: [{index: 0, word: "vest"}]
```

**Validation (load time, unchanged 016 `load_drill_bank`)**: structural — each drill references a known
`contrast_id`; each `targets.index` is in range of `canonical`; ≥1 base drill exists. The **semantic**
validation (every symbol scores clean) is the live harness (§7).

**Authoring constraint**: every `is_base: true` drill is a sentence (more than one word); word drills
are follow-ons. Sentences place the contrast on an unambiguous word-initial position.

## 2. Per-drill loop result (extended item dict)

The 016 drill-block item dict gains additive retry fields. The primary `flags` remain the **first**
attempt's flags (so `with_flags` semantics are unchanged); the retry outcome is a nested optional key.

```python
{
  "drill_id": "vw-sentence-01",
  "text": "We verify every value.",
  "prompt": "We verify every value.",
  "status": "scored",                  # scored | not_captured | error (016)
  "flags": [ {... 016 PhoneFlag dict ...} ],   # the FIRST attempt's flags
  "is_follow_on": false,
  "contrast_id": "v_w",
  # --- NEW (017), present only when a retry actually ran ---
  "retry": {
    "attempts": 2,                     # total attempts incl. the first (== 1 + retries used)
    "outcome": "improved" | "still_off" | "not_captured",
    "final_flags": [ ... ],            # the LAST attempt's flags (empty when improved/cleared)
  },
}
```

`retry` is omitted entirely when no retry ran (non-interactive, retries=0, or the first attempt was
clean) → a 016-shaped item dict. `outcome` is detection-level (research D2).

## 3. Drill-block result (returned by the coordinator + standalone, additive summary)

```python
{
  "engine_note": "...",                # 016
  "items": [ ... extended item dicts ... ],
  "summary": {
    "drills": 4, "with_flags": 2,
    "contrasts_practiced": ["v_w","th_s"],     # 016
    "retried": 2,                              # NEW: items that ran ≥1 retry
    "improved_on_retry": 1,                    # NEW: items whose flag cleared on retry
    "tricky_sounds": ["v_w"],                  # NEW: most-flagged contrast(s) this run (≤3)
  },
}
```

`None` ⇒ no drills (off / declined / unsafe / no capability) ⇒ no frontmatter key, no section
(byte-identical, 016).

## 4. Report rendering (`pronunciation/feedback.render_drills_section`, additive)

The existing Pronunciation section gains: a per-item retry line when present, and a closing "tricky
sounds" line when the summary has them. Detection-led + hedged (FR-006/016 calibration). Example:

```markdown
## Pronunciation drills

_Read-aloud practice. Detection (a sound was off) is reliable; any specific "heard as …"
guess is a suggestion, not a verdict._

- **We verify every value.**
  - The **v** in *verify* sounded off. _(suggestion: it may have come out closer to **w**)_
    - Tip: For 'v', press your top teeth on your bottom lip and add voice.
  - On retry: better — that sound is clear now ✓
- **vest** *(follow-up)* — clear ✓

_Tricky sounds this session: v vs w._
```

When no drills ran, the whole section is absent (no-drills report byte-identical).

## 5. Config keys (`config/loop_config.py`, additive optional)

| Key | Default | Validation |
|---|---|---|
| `pronunciation_tts_playback` | `true` | must be `bool`, else default |
| `pronunciation_retries` | `1` | `int` clamped to `[0, 3]`, else default |

(Join the 016 keys `pronunciation_drills` = auto/on/off and `pronunciation_min_free_mb` = 4500.)

## 6. Derived store section (`store/model.py`, additive; `STORE_VERSION` stays 1)

```python
@dataclass
class Store:
    ...
    # NEW: contrast_id -> chronological [iso_date, flagged_count] series (mirrors `patterns`)
    pronunciation_contrasts: dict[str, list[list]] = field(default_factory=dict)
```

- `to_dict()`/`from_dict()` round-trip it; `from_dict` defaults to `{}` for old stores; old code ignores
  the unknown key (forward/back-compatible).
- `store.rebuild` folds it from each report's `pronunciation_drills` (contrasts that were flagged →
  `[date, count]` appended), so the interview-session contribution is **rebuildable** from reports.
- Standalone runs append live (not in any report); a manual `rebuild` drops standalone-only history
  (documented; matches the SRS `next_due` precedent).

**Weak-contrast ordering input**: `weak_contrasts = sorted(contrast_ids by recent flagged_count desc)`
derived from this series; empty when no history → `select_drills` uses curated order.

## 7. Build-time correctness harness (`tests/live_pron_test.py`, live, self-skipping)

For every `drill` in `load_drill_bank()`:
```
wav = kokoro.synthesize(drill.prompt)
result = scorer.score(wav, canonical=drill.canonical, targets=drill.targets, ...)
assert result.status == "scored"
assert no flag at any drill.targets index   # a clean rendering must not be flagged
```
Marker `live_pron`; skips when the model/TTS are absent; excluded from the default suite (no model
loaded by `uv run pytest`).

## 8. Standalone safety decision (`gate.assess_standalone_safety`)

Reuses the 016 `SafetyDecision` dataclass. RAM-only: SAFE when `available_mb ≥ min_free_mb` or RAM
unreadable (safe-cautious); UNSAFE (low memory) below. `engine="standalone"`. No engine penalty. The
016 `assess_safety(engine,…)` is unchanged.

## State / lifecycle

### Interview drill block (sessions, concurrent with feedback — 016 path + 017 loop)
```
attempts done → drills permitted? (CLI-decided, 016 gate)
  └─ yes → start _analyze() in bg thread (quiet)        ┐
           for each base drill (weak-sound ordered):     │
             run_drill_item: hear → record → score        ├─ join → assemble report
               → (flagged & interactive) bounded retry    │   (+ pronunciation section w/ retry/tricky)
             flagged base → bounded follow-on minimal pairs│   → store: patterns + pronunciation_contrasts
           drill audio scored then discarded              ┘
```

### Standalone `pronounce` (cli, no feedback)
```
config → assess_standalone_safety (RAM-only; override on unsafe)
  → ensure_models("A") + ensure_pronunciation_model (decline → exit)
  → build scorer/bank/tts/play/record/key_reader; load store tally
  → user-paced loop: select_drills(weak) → run_drill_item per item; `q` quits
  → closing summary (count + tricky sounds) + store pronunciation_contrasts update (no report)
```
