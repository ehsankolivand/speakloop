# Contract: New language-model calls

Every new call below obeys the **same rules** (research R6, FR-039):

- It calls the **injected `LLMEngine.generate(system_prompt, user_prompt, max_tokens, temperature,
  retry)`** — never an engine package. Built once per session over the `--cloud`-selected engine.
- Its **system prompt** is a packaged default seeded into a user-editable file under `~/.speakloop/`
  (loader mirrors `cloud_prompt.load_coach_prompt`); read verbatim.
- Its output is **strict JSON** matching the schema here, parsed through the **existing recovery ladder**
  `grammar_analyzer._extract_json` (strict → first-`{...}` → `json_repair` → `json_repair` region). On a
  parse/validation failure it uses the existing **one bounded `retry=True`** regenerate, then raises
  `LLMEngineError`.
- On `LLMEngineError` the coordinator records a non-fatal `*_error` note and (where the datum is required
  for grading/coverage) sets `analysis_pending = True`. The recording and transcripts are already saved
  first — never lost (FR-035).
- The **reference/ideal answer is passed explicitly** only where noted; follow-ups never receive it
  (FR-001), mirroring how `coach` excludes it.
- `temperature` is the only generation knob passed by the call site (engine owns sampler/stop/penalty/
  thinking-mode). `retry` is boolean intent.

Validation common to all: top-level must be a JSON object; arrays default to empty on absence; every
string field is non-empty after strip or the item is dropped; unknown keys ignored.

---

## C1 — Follow-up generation (`interviewer/followups.py`, P1)

**Precondition (deterministic, no LLM)**: probe-worthy gate — combined real-speech transcript across the
three attempts ≥ 30 words (Key Definitions); else 0 follow-ups, `skipped_reason="no_probe_material"`.

**Input**: question text + the three **real-speech** attempt transcripts (post-triage when P4 present).
**Not** the ideal answer.

**Output JSON** (`max_tokens = 256`, `temperature = 0.4`):
```json
{ "followups": [
  { "question": "<spoken follow-up, references the learner's own words/omission>",
    "probe_ref": "<the learner word or the missed point it probes>",
    "probe_type": "gap" }   // gap | edge_case | why
] }
```
Count rule: 2 items when ≥ 2 distinct probe candidates exist, else 1, else 0 (Assumptions). Each
`question` must contain a content word (≥4 chars, non-stopword) from the transcripts, or name a missed
point (SC-010, enforced by a post-parse check; failing items dropped).

**Fallback**: `LLMEngineError` → no follow-up stage, `follow_ups=[]`, non-fatal `followups_error` note;
session still reported.

---

## C2 — Key-point derivation (`coverage/keypoints.py`, P3)

**Input**: question text + **ideal answer** + `question_type`. Triggered only when no cached
`KeyPointSet` exists for `(question_id, ideal_answer_hash)` (R3).

**Output JSON** (`max_tokens = 512`, `temperature = 0.2`):
```json
{ "key_points": ["<atomic assertion>", "..."] }
```
Count: 5–7 for `definition`/`hypothetical`; exactly 4 for `behavioral` (the STAR components, in S/T/A/R
order) (FR-018/FR-033). Stored under the ideal-answer hash with an incremented `key_points_version`.

**Fallback**: `LLMEngineError` → no key points → coverage skipped, `analysis_pending=True`,
`coverage_error` note. (Grammar/fluency still run; grade uses the fallback path.)

---

## C3 — Coverage + content errors (`coverage/scoring.py` + `content_errors.py`, P3)

**One call per session over all three attempts** (latency: avoids 3 calls).

**Input**: the `KeyPointSet` (point id + text) + the three **real-speech** attempt transcripts + the
**ideal answer** (for content-error detection). Coverage is judged against the stored key points.

**Output JSON** (`max_tokens = 1024`, `temperature = 0.2`):
```json
{ "attempts": [
    { "ordinal": 1, "coverage": [ { "id": 1, "state": "covered" } ] }   // state: covered|partial|missed
  ],
  "content_errors": [
    { "attempt_ordinal": 3, "learner_claim": "Android 11",
      "ideal_claim": "Android 12", "key_point_id": 2 }
] }
```
Validation: every key-point `id` must appear in each attempt's `coverage` (missing → `missed`); `state` ∈
the three literals; a content error requires both claims non-empty and *mutually exclusive* (omissions /
extra-correct facts are dropped — FR-021). Aggregate per attempt computed in code = (covered+0.5·partial)/N.

**Fallback**: `LLMEngineError` → `coverage=[]`, `content_errors=[]`, `analysis_pending=True`,
`coverage_error` note; grade uses the fallback path (grammar+fluency).

---

## C4 — Mishearing classification (`triage/mishearing.py`, P4)

Runs **after** the deterministic hallucination filter, only on **low-confidence real-speech tokens**
(word `probability` below threshold, or in a low `avg_logprob` segment), and only when an LLM is
available (enrichment).

**Input**: candidate spans (token text + a small surrounding window). **Not** the ideal answer.

**Output JSON** (`max_tokens = 256`, `temperature = 0.2`):
```json
{ "mishearings": [
  { "span_text": "the mouse keyword", "heard": "mouse", "likely_intended": "must" }
] }
```
Each flagged span becomes a `TriagedSpan(span_class="mishearing")` → Pronunciation flags section
(FR-026), never grammar. Hallucinations are **not** produced here (they were already removed,
deterministically, before grammar — FR-028/SC-003).

**Fallback**: `LLMEngineError` or no LLM → mishearing detection skipped; candidate spans stay `real`
(the hallucination guarantee is unaffected because it is heuristic and already applied).

---

## C5 — Artifact consistency check (`triage/consistency.py`, P4)

Applied to each **generated learning artifact** that a run actually produces, **before** the report is
written (FR-027): drill/warm-up sentences (both modes); the improved-answer rewrite and flashcards
(cloud-only, as today — spec Assumptions).

**Input**: the artifact text + the **ideal answer** (and/or the `KeyPointSet`).

**Output JSON** (`max_tokens = 512`, `temperature = 0.2`):
```json
{ "contradictions": [
  { "claim": "<claim in the artifact>", "ideal_claim": "<what the ideal answer says>",
    "fix": "<corrected text>", "drop": false }   // drop=true ⇒ remove the item entirely
] }
```
Resolution in code: apply `fix` where present, else drop the item; an artifact with no surviving
contradiction passes through unchanged. Result: 100% of written artifacts are consistent (SC-004).

**Fallback**: `LLMEngineError` → the artifact is **withheld** (not written) rather than risk an unchecked
contradiction, with a `consistency_error` note. (Wrong feedback is worse than none — spec P4 rationale.)

---

## C6 — Warm-up drill generation (`warmup/drill.py`, P2c)

**Input**: the top recurring-error label + its corrected/error forms (from the cross-session pattern
aggregation). Generates the drill; **judging is deterministic, no LLM** (FR-016).

**Output JSON** (`max_tokens = 512`, `temperature = 0.4`):
```json
{ "items": [
  { "target_sentence": "<one sentence the learner should say>",
    "corrected_form": "<the correct construction to detect>",
    "error_form": "<the error construction to detect>" }
] }
```
Exactly 3 items (Key Definitions). Judging (`warmup.judge_item`): `pass` iff the transcribed response
contains `corrected_form` and not `error_form`; `incomplete` iff empty/garbage/silent; else `fail`.

**Fallback**: `LLMEngineError`/no qualifying error/no LLM → warm-up skipped, `skipped_reason` set, loop
proceeds to attempt 1 (FR-016/FR-017).
