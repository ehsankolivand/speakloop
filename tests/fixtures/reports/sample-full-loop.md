---
schema_version: 1
session_id: 2026-06-10-rotation
started_at: '2026-06-10T09:00:00'
question_id: activity-rotation-callbacks
question: |
  Walk me through what happens to an Activity when the user rotates the device.
ideal_answer: |
  By default a rotation is a configuration change; the Activity is torn down and recreated; the ViewModel survives; Android 12 changed trace collection.
attempts:
- ordinal: 1
  time_budget_seconds: 240
  actual_duration_seconds: 210.0
  metrics:
    words_total: 70
    speech_rate_wpm: 84.0
    filler_words_count: 3
    filler_density_per_100_words: 4.3
    pauses_count: 4
    mean_pause_ms: 520.0
    self_corrections_count: 1
- ordinal: 2
  time_budget_seconds: 180
  actual_duration_seconds: 170.0
  metrics:
    words_total: 70
    speech_rate_wpm: 90.0
    filler_words_count: 3
    filler_density_per_100_words: 4.3
    pauses_count: 4
    mean_pause_ms: 520.0
    self_corrections_count: 1
- ordinal: 3
  time_budget_seconds: 120
  actual_duration_seconds: 115.0
  metrics:
    words_total: 70
    speech_rate_wpm: 98.0
    filler_words_count: 3
    filler_density_per_100_words: 4.3
    pauses_count: 4
    mean_pause_ms: 520.0
    self_corrections_count: 1
grammar_patterns:
- label: subject-verb agreement
  occurrence_count: 1
  impact_rank: 1
  explanation: Use the singular verb form after a singular subject.
  evidence:
  - attempt_ordinal: 1
    quote: when the phone rotate
    corrected: when the phone rotates
generated_by_phase: C
cross_attempt_narrative: |-
  Your speech rate climbed from 84 to 98 WPM across the three attempts.
top_priority: |-
  Lock in third-person singular verb agreement under time pressure.
warmup:
  target_pattern: subject-verb agreement
  items:
  - index: 1
    target_sentence: The system creates a new Activity.
    result: pass
  - index: 2
    target_sentence: The phone rotates and the state saves.
    result: fail
  - index: 3
    target_sentence: The ViewModel survives the change.
    result: pass
follow_ups:
- index: 1
  question_text: Why does the ViewModel survive the configuration change?
  probe_ref: ViewModel
  answered: true
  transcript: Because it is stored in the retained non configuration instance, so
    it is not cleared.
  metrics:
    words_total: 17
    speech_rate_wpm: 88.0
  grammar_patterns:
  - label: article use
    occurrence_count: 1
    from_followup: true
    evidence:
    - quote: in retained instance
      corrected: in the retained instance
- index: 2
  question_text: What happens to the bundle if the OS kills the process?
  probe_ref: edge_case
  answered: false
coverage:
- attempt_ordinal: 1
  key_points_version: 1
  aggregate: 0.25
  per_point:
  - id: 1
    state: covered
  - id: 2
    state: missed
  - id: 3
    state: missed
  - id: 4
    state: missed
- attempt_ordinal: 3
  key_points_version: 1
  aggregate: 0.875
  per_point:
  - id: 1
    state: covered
  - id: 2
    state: covered
  - id: 3
    state: covered
  - id: 4
    state: partial
content_errors:
- attempt_ordinal: 3
  learner_claim: Android 11
  ideal_claim: Android 12
  key_point_id: 4
pronunciation_flags:
- attempt_ordinal: 2
  heard: mouse
  likely_intended: must
  signal: llm_mishearing
key_points:
  version: 1
  ideal_answer_hash: abc123
  question_type: definition
  points:
  - id: 1
    text: rotation is a configuration change
  - id: 2
    text: the Activity is destroyed and recreated
  - id: 3
    text: the ViewModel survives the change
  - id: 4
    text: Android 12 changed trace collection
answer_grade: good
triage_summary:
  real: 9
  mishearing: 1
  hallucination_dropped: 1
pattern_trends:
  subject-verb agreement: 5 → 3 → 1
---

# activity-rotation-callbacks — 2026-06-10

## Question & reference answer

**Question:** Walk me through what happens to an Activity when the user rotates the device.

**Reference answer:**

By default a rotation is a configuration change; the Activity is torn down and recreated; the ViewModel survives; Android 12 changed trace collection.

## Top priority for next session

Lock in third-person singular verb agreement under time pressure.

## Attempt-by-attempt summary

| Round | Budget | Used | WPM | Fillers/100w | Pauses |
|-------|--------|------|-----|--------------|--------|
| 1     | 4:00   | 3:30 | 84 | 4.3          | 4     |
| 2     | 3:00   | 2:50 | 90 | 4.3          | 4     |
| 3     | 2:00   | 1:55 | 98 | 4.3          | 4     |

## Cross-attempt comparison

Your speech rate climbed from 84 to 98 WPM across the three attempts.

## Grammar patterns

### subject-verb agreement *(1×)*
- **You said:** “when the phone rotate”
- **Better:** “when the phone rotates”
- **Because:** Use the singular verb form after a singular subject.
- **Trend (recent sessions):** 5 → 3 → 1

## Warm-up drill

_Exercising your recurring pattern: **subject-verb agreement**._

- ✓ The system creates a new Activity. — **pass**
- ✗ The phone rotates and the state saves. — **fail**
- ✓ The ViewModel survives the change. — **pass**

## Content coverage

_Final-round goal: all key points within the time budget._

| Key point | R1 | R3 |
|---|---|---|
| rotation is a configuration change | ✓ | ✓ |
| the Activity is destroyed and recreated | ✗ | ✓ |
| the ViewModel survives the change | ✗ | ✓ |
| Android 12 changed trace collection | ✗ | ~ |

**Coverage:** 25% (R1) → 88% (R3), Δ +62%

## Content errors (vs. reference answer)

- You said **Android 11**, but the reference answer says **Android 12**. *(round 3)*

## Pronunciation flags

_These look like the recognizer mishearing a word you said — practice the pronunciation; they are not grammar mistakes._

- heard **“mouse”** — likely you meant **“must”**

## Follow-ups

### Follow-up 1

**Interviewer:** Why does the ViewModel survive the configuration change?

**You said:** Because it is stored in the retained non configuration instance, so it is not cleared.

- article use *(1×)*

### Follow-up 2

**Interviewer:** What happens to the bundle if the OS kills the process?

_No answer — timed out._

## Transcripts

### Attempt 1

So when the phone rotate the activity is destroyed and the system make a new one.


### Attempt 2

On rotation the activity is destroyed and recreated, and onSaveInstanceState saves the bundle.


### Attempt 3

Rotation is a configuration change; the ViewModel survives via the retained instance.
