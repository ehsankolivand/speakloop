# Data Model: Reliable, Higher-Quality Session Feedback

**Feature**: 006-feedback-quality-reliability · **Date**: 2026-05-22 · **Phase**: 1

This sprint changes **how existing data is populated and recovered**, not the persisted
report schema. The session-report frontmatter schema stays at `schema_version: 1`
(`feedback/frontmatter.py:11`, FR-018). The only genuinely new data lives **outside the
shipped package**, in the validation harness (`eval/`), and never reaches an end user.

Legend: 🟢 unchanged shape · 🟡 transient (in-process only) · 🆕 new validation artifact.

---

## 1. GrammarPattern 🟢 (unchanged shape — `feedback/frontmatter.py:14`)

The persisted finding. **No field is added, removed, renamed, or retyped.** Quality work
changes the *values* the analyzer puts here, not the structure.

| Field | Type | Notes |
|-------|------|-------|
| `label` | str | Catalog label (canonicalized) or open-bucket label |
| `occurrence_count` | int | Across attempts |
| `evidence` | list[dict] | Each: `attempt_ordinal:int`, `quote:str`, optional `corrected:str` |
| `explanation` | str? | "Because:" line; catalog `transfer_reason` or open-bucket reason |
| `impact_rank` | int? | 1 = highest; deterministic from catalog (or `OPEN_BUCKET_IMPACT_RANK`) |
| `catalog_id` | str? | Set on catalog match; None for open-bucket |
| `suggested_fix` | str? | Legacy optional |

**Invariants preserved (the existing verification pipeline — must remain true):**
- V1 **Verbatim**: every `evidence.quote` is a substring of its attempt transcript (FR-009; `grammar_analyzer.py:203`).
- V2 **Coherent**: each quote survives the deterministic ASR-garble filter (FR-009; `coherence.py`).
- V3 **No no-op fix**: a `corrected` equal to its `quote` is dropped; a pattern whose only fix is a no-op is suppressed (FR-010; `grammar_analyzer.py:211,218`).
- V4 **Open-bucket gate**: non-catalog patterns require `occurrence_count >= 2` and a non-empty explanation (`grammar_analyzer.py:230`).
- V5 **Deterministic order**: sorted by `(impact_rank, -occurrence_count, first_attempt_ordinal)` (FR-012 input; `grammar_analyzer.py:251`).

> These five invariants are the project's existing precision guarantees. This sprint
> **strengthens what reaches them** (better recall/precision *before* verification) and
> **must not weaken any of them**.

---

## 2. Raw grammar payload 🟡 (model-emitted, transient — the structured-output contract)

What the LLM is asked to emit, before verification. Kept **flat** (research Axis 2 §4 — flat
JSON has the lowest 4-bit malformation risk). See `contracts/grammar-output-schema.md`.

```json
{"patterns": [
  {"label": "...", "occurrence_count": 2, "explanation": "...",
   "evidence": [{"attempt_ordinal": 1, "quote": "...", "corrected": "..."}]}
]}
```

**Recovery ladder** (research Axis 3 decision tree) — applied in-process, never persisted:
1. `json.loads` on the fence-stripped text.
2. On failure → `json-repair` (schema-guided where available).
3. On repetition-loop detection / truncation → one bounded regenerate with
   `repetition_penalty` raised and temperature lowered.
4. Terminal failure → existing graceful fallback (`phase_c_error` set, Phase-B report).

`<think>` leakage and EOS handling stay inside the engine wrapper (`qwen_engine.py`).

---

## 3. Analysis recovery outcome 🟡 (in-process only — NOT persisted this sprint)

The harness and console observe how each analysis resolved:
`clean | repaired | regenerated | failed_fallback`. This is **runtime telemetry**, not a
report field. **Decision (FR-014, FR-018): do not add a persisted frontmatter key this
sprint** — the normal report stays byte-identical. If post-hoc diagnosis from saved files is
ever needed, the additive-only path is an optional top-level key emitted *only* on non-clean
paths (mirroring how `phase_c_error` is emitted only on failure); deferred, not built now.

---

## 4. Held-out evaluation set 🆕 (`eval/grammar/cases/*.yaml` — validation artifact, not shipped)

≈20–30 labeled cases used only to measure grammar agreement (FR-020, SC-002). Lives at the
**repository root under `eval/`, outside `src/speakloop/`**, so it can never be imported by
the CLI or shipped as a feature. Format: YAML (Constitution: user/data config is YAML).

```yaml
# eval/grammar/cases/case-001.yaml
id: case-001
source: synthetic            # synthetic | deidentified   (NEVER a real recording)
l1: persian                  # first language being simulated
transcripts:                 # 1–3 attempt texts (the analyzer takes a list)
  - "I am working on this project since two years..."
gold_issues:                 # human-labeled ground truth
  - attempt_ordinal: 1
    quote: "since two years"      # MUST be a verbatim substring of that transcript
    label: preposition            # catalog label OR explicit open-bucket label
    correction: "for two years"
    explanation: "Use 'for' with a duration."
notes: "Adjudication notes for ambiguous calls."
```

**Validation rules (enforced by a harness check):**
- E1 every `gold_issues[].quote` is a verbatim substring of the referenced transcript (mirrors V1).
- E2 every `label` is a catalog label or is explicitly tagged open-bucket (taxonomy = `feedback/persian_l1_catalog.yaml` + open).
- E3 **no personal data**: no real names, no audio, no maintainer paths (Principle III; 004 path-portability audit must still pass over `eval/`).
- E4 case count 20 ≤ N ≤ 30; each case has ≥1 transcript; correct cases (empty `gold_issues`) are allowed and encouraged (they measure false-alarm rate).

A sibling `eval/grammar/PROTOCOL.md` records the labeling rubric (what counts as an error,
the taxonomy, how ambiguity is adjudicated). A `README.md` explains provenance and de-identification.

---

## 5. Baseline / post-change record 🆕 (`eval/grammar/baselines/*.yaml`)

The before/after measurement that makes SC-001 and SC-002 falsifiable.

```yaml
# eval/grammar/baselines/baseline-pre.yaml
captured_at: 2026-05-2x
phase: pre            # pre | post
model_id: mlx-community/Qwen3-8B-4bit
quant: 4bit
eval_set_version: <git-sha-or-tag of eval/grammar/cases at capture time>
runs_per_case: 3              # K repeated runs; values below are the per-unit median (temp 0.7 is stochastic)
failure_batch_size: 120       # ≥100 synthetic/replayed sessions (no labels); makes a ~1% rate observable
failure_rate: 0.NN            # share of the failure batch with failed/unusable analysis (SC-001)
n_labeled_cases: 25           # the 20–30 labeled cases, used for agreement only
grammar:
  precision: 0.NN             # AI issues that match a gold issue
  recall: 0.NN                # gold issues the AI found
  f05: 0.NN                   # F0.5 (GEC convention: precision-weighted)
```

`pre` is captured against **today's code** before any change ships (FR-020). `post` is
captured after, against the same `eval_set_version`. SC-001/SC-002 compare the two.

---

## 6. Agreement score & failure rate 🟡 (computed by the harness)

Two instruments: agreement (precision/recall/F0.5) is scored on the **20–30 labeled cases**; the
**failure rate** is measured on a **separate, larger unlabeled batch** (a 20–30 case set cannot
observe a ~1% rate). Each unit is run **K ≈ 3 times** at temperature 0.7 and the per-unit
**median/mean** is used — seeding alone is insufficient under sampling.

- **Matching rule** (labeled set): a predicted GrammarPattern evidence item matches a gold issue iff it is
  on the same `attempt_ordinal`, the quotes **overlap** (predicted ⊆ gold or gold ⊆ predicted,
  case-insensitive), **and** the labels are compatible (same catalog id, or both open-bucket
  of the same surface type). One gold issue matches at most one prediction.
- **Metrics (SC-002)**: precision = matched / predicted; recall = matched / gold; **F0.5** weights
  precision (a false alarm is worse than a near-miss for a learner — research Axis 3 framing).
  **Pass bar**: F0.5 must clear the pre-registered improvement threshold **and** neither precision
  nor recall may fall below baseline (no regression on either axis).
- **Failure rate (SC-001)**: measured over a **separate batch of ≥100 synthetic/replayed sessions**
  (`eval/grammar/failure_batch/*.yaml` — same transcript shape as a case file, minus `gold_issues`;
  no human labels, because failure detection needs none). A session counts as a failure when the
  analyzer raises, returns unusable/garbled output, or the report would fall back to Phase-B
  (SC-001, SC-004).

---

## Relationships

```
cases/*.yaml (20–30 labeled)      ─(replay, K≈3)→ analyze() → predicted[] → Agreement §6 → SC-002
failure_batch/*.yaml (≥100, unlabeled) ─(replay, K≈3)→ analyze() → clean|failed → failure_rate → SC-001
                                  │
                                  ▼
                 baselines/{baseline-pre,post}.yaml  ──▶ SC-001 / SC-002 verdict
```

No edge above touches the network (Principle II). The harness calls the **already-downloaded**
local model; if absent, it reports "model unavailable" and is skipped (not a network fetch).
