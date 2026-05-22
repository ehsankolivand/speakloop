# Phase 0 Research: Reliable, Higher-Quality Session Feedback

**Feature**: 006-feedback-quality-reliability · **Date**: 2026-05-22

## Source of truth & method

`doc/QWEN_IMPROVMENT_RESEARCH.md` is the authoritative source for configuration, prompt-design,
and output-recovery decisions (per the planning brief and spec Assumptions). It was read in full.
Its **Verified** findings are lifted below as already-resolved decisions with citations. New
research was generated **only** for items the doc itself labels "Open Empirical Question",
"Inferred", "Extrapolated", or "Potentially outdated" — and of those, only one (the Outlines
rep-penalty gap) was web-researchable; the rest require on-device measurement and become harness
tasks, not blocking decisions.

---

## Part 1 — Lifted verified findings (already-resolved)

> Decision / Rationale / Source. "Status vs code" notes whether the repo already complies.

**R1 — Sampler values (non-thinking).** Use `temperature=0.7, top_p=0.8, top_k=20, min_p=0`;
never greedy. **Status vs code**: `top_p/top_k/min_p` already correct in `qwen_engine.py`, but the
grammar call site forces `temperature=0.2` — **must change to 0.7**. *Source*: Qwen3-8B model card
"Best Practices", https://huggingface.co/Qwen/Qwen3-8B (research Axis 1 §1, Rec 1).

**R2 — Repetition control.** Add `repetition_penalty=1.05, repetition_context_size=40` via
mlx-lm's `make_logits_processors`; mlx-lm's default `1.0` is a no-op and 4-bit Qwen3 is loop-prone.
**Status vs code**: **absent today** — this is the direct fix for the "repetitive suggestions"
complaint. *Source*: mlx-lm `SERVER.md` defaults; mlx-lm #844; research Rec 5.

**R3 — Thinking off for grammar.** `enable_thinking=False` for grammar (a pattern-completion +
edit task). **Status vs code**: already set inside `qwen_engine._build_prompt` ✅ (and the analyzer
guards against `<think>` leakage). *Source*: Qwen3-8B card; research Axis 2 §1, Rec 2.

**R4 — Version pins.** mlx-lm ≥ 0.31.3, mlx ≥ 0.31.0; do **not** use mlx 0.30.4 (Qwen3 garbage
past ~1000 tokens, #844); do **not** pass `--draft-model` with Qwen3 (#846). **Status vs code**:
`pyproject.toml` already pins `mlx-lm>=0.31.3` ✅ (mlx arrives transitively ≥ 0.31.2); no speculative
decoding is used ✅. *Source*: mlx-lm releases (v0.31.3, 2026-04-22); research Rec 3–4.

**R5 — Defensive EOS.** Pass `stop=["<|im_end|>"]`. **Status vs code**: absent — add it.
*Source*: `mlx-community/Qwen3-8B-4bit` tokenizer config; research Rec 10.

**R6 — max_tokens budget.** Cap at ≈ 4× input; ~2048 for paragraph-level grammar; longer caps
just enlarge the repetition tail. **Status vs code**: fixed 2048 today — acceptable upper bound;
keep ≤ 2048. *Source*: Qwen3-8B card; research Rec 6.

**R7 — Output format = minimal flat JSON.** Lowest 4-bit malformation risk; avoid nested
`oneOf`/optional objects (schema drift). **Status vs code**: prompt is already close (flat
`patterns[]`); keep flat, ≤ 2 few-shot examples. *Source*: research Axis 2 §3–4, Rec 12.

**R8 — Output-repair library inventory.** lm-format-enforcer, XGrammar, Guidance have **no
working mlx-lm backend** → excluded. Viable: `json-repair` (post-hoc) or Outlines `mlxlm`
(decode-time). *Source*: their READMEs; research Axis 3 §3–6.

**R9 — Recovery decision tree.** parse → `json-repair` → bounded regenerate (rep-penalty↑,
temp↓) on loop/length → graceful fallback. Lifted verbatim into `contracts/grammar-output-schema.md`
§C. *Source*: research "Output-repair decision tree".

---

## Part 2 — Three explicit planning decisions

### Decision 1 — Thinking mode / call-site topology: **single mode, narrative stays deterministic**

**Decision.** There is exactly **one** LLM call site (grammar analysis), run with
`enable_thinking=False`. The **cross-attempt narrative and top-priority remain deterministic**
(no LLM). "Dual-mode thinking" is therefore **not adopted** this sprint — there is no second call
site to run in thinking mode.

**Rationale.**
- **FR-012** requires the top-priority to be a *stable, explainable, reproducible* rule, "never an
  arbitrary or near-random pick." An LLM selection is none of those — keeping it deterministic
  satisfies FR-012 by construction. (The "near-random" complaint is an *input-quality* problem:
  the deterministic rule selects from a noisy issue list; fixing grammar quality fixes the pick.)
- **FR-011** requires the narrative to invent no unsupported fact. A deterministic narrative is
  grounded by construction; an LLM narrative would reintroduce exactly the hallucination risk the
  spec warns against.
- **SC-001 reliability**: a second LLM call site doubles the failure surface. One call site is
  more reliable.
- **Constitution** "boring over novel": the deterministic narrative already exists and works.
- The narrative complaint is met by (a) better grammar inputs and (b) tightening the deterministic
  prose to strict grounding (`contracts/report-invariance.md` "what may change").

**Encapsulation (Constitution V).** `enable_thinking=False` already lives inside
`qwen_engine._build_prompt`; call sites never set it. If a future sprint adds an LLM-authored,
grounded narrative (a genuine reasoning task warranting `enable_thinking=True`), the mode MUST be a
**wrapper-internal per-call parameter**, never set at the call site. Recorded as the deferred
dual-mode design.

**Alternatives rejected.** (a) LLM narrative + top-priority with thinking on — violates
FR-011/FR-012, adds failure surface, novel. (b) Thinking on for grammar — grammar is
pattern-completion (research Axis 2 §1); wastes the 4-bit budget.

### Decision 2 — Quantization: **stay on 4-bit; 8-bit evaluation is out of scope this sprint**

**Decision.** Ship and keep **`mlx-community/Qwen3-8B-4bit`** (status quo, `manifest.py:63`). The
8-bit variant (`mlx-community/Qwen3-8B-8bit`) is **explicitly out of scope** — it is not evaluated,
not A/B-tested, and not adopted this sprint. There is **no adoption threshold**. Any future 8-bit
consideration belongs in a **separate sprint** under its own decision record.

**Rationale.**
- **Bandwidth/cost (Constitution VI).** 8-bit adds **~4 GB** to every user's download. In the target
  deployment region, metered/VPN bandwidth makes that a real per-user cost — exactly the
  unreliable-internet case Principle VI exists to protect.
- **RAM (Constitution VII).** Apple Silicon machines are frequently 8/16 GB unified; doubling the
  model footprint pressures the very hardware we target.
- **No measured benefit to weigh against that cost.** The research has **no GEC numbers for 8-bit**
  (the general-capability deltas and "8-bit ≈ lossless" are *extrapolated*, not measured for grammar).
  Spending real user bandwidth/RAM for an unmeasured gain is the wrong trade for this user.

**FR-017 stays absolute.** No carve-out is added — "no model swap" remains exactly as written. (A
future sprint that revisits 8-bit does so under its own decision, not by reinterpreting FR-017 here.)
*Source*: Constitution VI/VII; research Axis 1 §7, Rec 7 (the doc itself: "reserve 4-bit for memory
pressure" — our user is that case).

### Decision 3 — Structured-output strategy: **`json-repair` now; Outlines deferred**

**Decision.** This sprint uses **`json-repair`** (post-hoc safety net) paired with mlx-lm's native
`repetition_penalty`/`logits_processors`, replacing the brittle hand-rolled regex repair. Outlines's
`mlxlm` decode-time constrained generation is documented as the **future-iteration fallback** for
hard schema guarantees if json-repair proves insufficient.

**Rationale — with a correction to the research doc (see Part 3).** The doc deferred Outlines because
its `mlxlm` backend "lacks rep-penalty" (issue #1131) → infinite-loop JSON. **That claim is now
outdated**: #1131 was resolved (PR #1134, merged 2025-06-18) and current Outlines (v1.3.0) forwards
`repetition_penalty` to mlx-lm via its `**kwargs`/`logits_processors` passthrough. So the deferral now
rests on **different, honest grounds**:
- `json-repair` is a **smaller, pure-Python, zero-required-dependency** change (PyPI 0.59.10,
  2026-05-14; offline-safe) that pairs with the recovery ladder and the rep-penalty we enable anyway.
- Outlines is **decode-time enforcement** — a larger architectural step (must be wrapped to honor
  Principle V; heavier dependency tree). For a *reliability* sprint we minimize blast radius.
- `json-repair` **removes ~5 brittle regexes** (`_repair_json`, `_loads_lenient`, optional `json5`):
  "boring over novel" in the good sense.

**New dependency (flagged per spec Assumption).** `json-repair` is the **one** new third-party
dependency this sprint; offline pure-Python, no `[schema]` extra needed for the flat schema.
Justified by SC-001/SC-004 and the simplicity gain. **No-dependency fallback** if the maintainer
vetoes it: harden the existing regex repair (accepts more custom code). *Source*: research Axis 3
§2,6; https://github.com/mangiucugna/json_repair.

---

## Part 3 — Re-verification of one "Potentially outdated" item (done)

The doc flagged the Outlines #1131 rep-penalty gap as "documented from late 2024–2025; check current
release notes." A focused web re-verification (2026-05-22) found:

- **Outlines #1131 is RESOLVED** — PR #1134 (merged **2025-06-18**) added
  `repetition_penalty`/`repetition_context_size`; current Outlines **v1.3.0** (PyPI, 2026-05-13)
  reaches repetition control through the `mlxlm` backend's `**kwargs`/`logits_processors` passthrough
  to mlx-lm's `make_repetition_penalty`. *Sources*: github.com/dottxt-ai/outlines/issues/1131,
  /pull/1134, /blob/main/outlines/models/mlxlm.py; pypi.org/project/outlines/ (all fetched 2026-05-22).
- **json-repair v0.59.10** (2026-05-14) confirmed pure-Python, zero required runtime deps, offline.
  *Source*: pypi.org/project/json-repair/.

**Effect**: does not flip Decision 3 (json-repair still wins on footprint/blast-radius), but corrects
its rationale and strengthens Outlines as a viable *future* option. The research doc's "Outlines lacks
rep-penalty" line should be treated as superseded.

---

## Part 4 — Open Empirical Questions → on-device measurement tasks (not blocking)

These require the local model + a labeled corpus; they are resolved by the harness, not by web
research, and they do **not** block implementation. They are pre-registered so /speckit-tasks can
schedule them.

- **M1 (doc Open Q1)** — malformation/failure rate of the flat schema on the ≥100-session unlabeled
  failure batch (not the 20–30 labeled set, which can't resolve ~1%) →
  measured as `failure_rate` (SC-001) at baseline and post.
- **M2 (doc Open Q2)** — does `repetition_context_size=40` vs `20` materially cut loops? → A/B in the
  harness *only if* loops persist after R2; otherwise keep 40.
- **M3 (doc Open Q4) — DEFERRED to a future sprint.** 4-bit vs 8-bit grammar agreement is **not**
  measured this sprint: 8-bit is out of scope (Decision 2). Recorded here only so a future sprint
  that revisits quantization can pick it up.
- **M4 (doc Open Q3)** — Outlines vs json-repair on this model → revisited **only** if json-repair is
  insufficient (Decision 3 deferral).

## Part 5 — Inferred / Extrapolated items → adopted as low-risk defaults

- ≤ 2 few-shot examples; flat schema (Inferred) → adopted; revisit if schema drift appears (R7).
- Working budget ~16K input / 1–4K output on 8 GB; `max_tokens ≤ 2048` (Inferred) → adopted (R6).
- Quantization quality delta extrapolated to GEC → not relied upon; 8-bit evaluation is **deferred to
  a future sprint** (Decision 2 / M3).

## Part 6 — Two spec Assumptions lifted into explicit tasks

- **A-Baseline** — Before any code change ships, capture today's `failure_rate` (over the failure
  batch) and grammar agreement (over the labeled set) on **current** code (`phase: pre`). Required
  for SC-001/SC-002 to be measurable. (FR-020.)
- **A-EvalSet** — Build `eval/grammar/` as a sprint deliverable: 20–30 labeled cases, a ≥100-session
  unlabeled failure batch (`failure_batch/`, for SC-001), `PROTOCOL.md`
  (labeling rubric + taxonomy), `README.md` (provenance/de-identification), and `run_eval.py`
  (validate-only + measure modes). Per `contracts/eval-set-format.md`. (FR-020, SC-001, SC-002.)

---

## Net impact summary

| Axis | Result |
|------|--------|
| New dependencies | **+1**: `json-repair` (offline, pure-Python, zero required deps) — flagged |
| Report schema | **unchanged** (`schema_version: 1`, additive-only policy intact) |
| Network | **none added** (Principle II) — harness uses the local model only |
| Engine boundary | sampler/rep-penalty/stop/thinking stay **inside `qwen_engine.py`** (Principle V) |
| Narrative/top-priority | stay **deterministic** (Decision 1) |
| Model | **`mlx-community/Qwen3-8B-4bit` unchanged; 8-bit out of scope this sprint** (Decision 2) |
| New code outside package | `eval/` (validation only; not shipped) |

All NEEDS CLARIFICATION resolved. No blocking unknowns remain.
