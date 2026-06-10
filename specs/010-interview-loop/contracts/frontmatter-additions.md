# Contract: Session-report frontmatter additions

All keys below are **additive and optional**, emitted only when present, and ignored by older readers.
The report **`schema_version` stays `1`** (research R7); old reports parse unchanged (SC-012). Transcript
text (warm-up responses, follow-up answers) is **body-only**, like attempt transcripts and `coaching`.
Pattern: same as the existing `asr:` / `coach_error:` additive keys (`frontmatter.py:199-212`).

## New top-level keys (illustrative)

```yaml
schema_version: 1            # UNCHANGED
question_id: anr-on-startup
question_type: hypothetical  # NEW (default "definition" when absent)

# NEW — P3 coverage, per attempt + the key-point set scored against
key_points:
  version: 2
  ideal_answer_hash: "9f2c…"
  points:
    - { id: 1, text: "ANR fires when the main thread is blocked > 5s" }
    - { id: 2, text: "move the work off the main thread" }
coverage:
  - attempt_ordinal: 1
    aggregate: 0.40
    per_point: [ { id: 1, state: covered }, { id: 2, state: missed } ]
  - attempt_ordinal: 3
    aggregate: 0.90
    per_point: [ { id: 1, state: covered }, { id: 2, state: covered } ]
content_errors:
  - { attempt_ordinal: 3, learner_claim: "Android 11", ideal_claim: "Android 12", key_point_id: 2 }

# NEW — P4 pronunciation flags (mishearings); hallucinations are excluded entirely, never listed as grammar
pronunciation_flags:
  - { attempt_ordinal: 2, heard: "mouse", likely_intended: "must", signal: "llm_mishearing" }
triage_summary: { real: 41, mishearing: 1, hallucination_dropped: 2 }

# NEW — P2c warm-up (item transcripts are body-only)
warmup:
  target_pattern: "modal + base verb"
  items:
    - { index: 1, target_sentence: "You must restart the service.", result: pass }
    - { index: 2, target_sentence: "It must run on the main thread.", result: fail }
    - { index: 3, target_sentence: "We must handle the exception.", result: incomplete }

# NEW — P1 follow-ups (answer transcripts are body-only; grammar feeds trends tagged as follow-up)
follow_ups:
  - index: 1
    question_text: "You mentioned the main thread — why does blocking it cause an ANR specifically?"
    probe_ref: "main thread"
    answered: true
    metrics: { words_total: 38, speech_rate_wpm: 95.0, filler_words_count: 2, … }
    grammar_patterns: [ … ]               # same shape as the existing grammar_patterns
  - index: 2
    question_text: "What would you do if the work can't be moved off the main thread?"
    probe_ref: "edge_case"
    answered: false                        # timed out or skipped (FR-003/FR-002a)

# NEW — SRS grade + degradation
answer_grade: good                         # poor|fair|good|strong (drives scheduling)
analysis_pending: false                    # true ⇒ `speakloop resume` re-runs analysis (FR-035a)
```

## Round-trip & rules

- `frontmatter.dump` emits each key only when its value is present/non-default; `frontmatter.parse`
  defaults every new key to `None`/empty/`False`. `dump → parse → dump` stays idempotent.
- Body-only fields (`warmup.items[].transcript`, `follow_ups[].transcript`) are rendered into the report
  body and **not** serialized to YAML — like attempt transcripts and `coaching` today.
- `ideal_answer` stays human-only; it is **never** passed into any analytic LLM call (existing trap) —
  the coverage/content-error/consistency calls receive it explicitly as a parameter, the rest never.
- `report_builder.build` renders new sections (Warm-up → Coverage → Content errors → Pronunciation flags
  → Follow-ups → type guidance) after the grammar section and before transcripts; absent data ⇒ no
  section ⇒ byte-identical to a pre-feature report.
