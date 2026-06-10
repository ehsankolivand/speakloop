---
schema_version: 1
session_id: 2026-06-10-behavioral-anr-debugging
started_at: '2026-06-10T09:00:00'
question_id: behavioral-anr-debugging
question: |
  Tell me about a time you debugged a difficult ANR.
ideal_answer: |
  Cover Situation, Task, Action, and Result; past tense; quantified result.
attempts:
- ordinal: 1
  time_budget_seconds: 240
  actual_duration_seconds: 205.0
  metrics:
    words_total: 70
    speech_rate_wpm: 82.0
    filler_words_count: 3
    filler_density_per_100_words: 4.3
    pauses_count: 4
    mean_pause_ms: 520.0
    self_corrections_count: 1
- ordinal: 2
  time_budget_seconds: 180
  actual_duration_seconds: 165.0
  metrics:
    words_total: 70
    speech_rate_wpm: 89.0
    filler_words_count: 3
    filler_density_per_100_words: 4.3
    pauses_count: 4
    mean_pause_ms: 520.0
    self_corrections_count: 1
- ordinal: 3
  time_budget_seconds: 120
  actual_duration_seconds: 118.0
  metrics:
    words_total: 70
    speech_rate_wpm: 97.0
    filler_words_count: 3
    filler_density_per_100_words: 4.3
    pauses_count: 4
    mean_pause_ms: 520.0
    self_corrections_count: 1
grammar_patterns:
- label: past tense
  occurrence_count: 2
  impact_rank: 1
  explanation: Behavioral answers need consistent past tense.
  evidence:
  - attempt_ordinal: 1
    quote: I am look into it
    corrected: I looked into it
generated_by_phase: C
cross_attempt_narrative: |-
  Your speech rate climbed from 82 to 97 WPM; past-tense slips fell across rounds.
top_priority: |-
  Keep every verb in the past tense when telling a STAR story.
question_type: behavioral
warmup:
  target_pattern: past tense
  items:
  - index: 1
    target_sentence: I fixed the crash last week.
    result: pass
  - index: 2
    target_sentence: I am fixed the bug.
    result: fail
  - index: 3
    target_sentence: I moved the work off the main thread.
    result: pass
follow_ups:
- index: 1
  question_text: You said the main thread was blocked — how did you confirm that specifically?
  probe_ref: main thread
  answered: true
  transcript: I read the ANR trace and saw the main thread stuck in a synchronous
    read.
  metrics:
    words_total: 15
    speech_rate_wpm: 90.0
  grammar_patterns: []
- index: 2
  question_text: What would you do if it only reproduced on low-end devices?
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
pronunciation_flags:
- attempt_ordinal: 1
  heard: freeze
  likely_intended: frozen
  signal: llm_mishearing
key_points:
  version: 1
  ideal_answer_hash: star01
  question_type: behavioral
  points:
  - id: 1
    text: Situation
  - id: 2
    text: Task
  - id: 3
    text: Action
  - id: 4
    text: Result
answer_grade: good
triage_summary:
  real: 12
  mishearing: 1
  hallucination_dropped: 1
pattern_trends:
  past tense: 8 → 4 → 2
---

# behavioral-anr-debugging — 2026-06-10

## Question & reference answer

**Question:** Tell me about a time you debugged a difficult ANR.

**Reference answer:**

Cover Situation, Task, Action, and Result; past tense; quantified result.

## Top priority for next session

Keep every verb in the past tense when telling a STAR story.

## Attempt-by-attempt summary

| Round | Budget | Used | WPM | Fillers/100w | Pauses |
|-------|--------|------|-----|--------------|--------|
| 1     | 4:00   | 3:25 | 82 | 4.3          | 4     |
| 2     | 3:00   | 2:45 | 89 | 4.3          | 4     |
| 3     | 2:00   | 1:58 | 97 | 4.3          | 4     |

## Cross-attempt comparison

Your speech rate climbed from 82 to 97 WPM; past-tense slips fell across rounds.

## Grammar patterns

### past tense *(2×)*
- **You said:** “I am look into it”
- **Better:** “I looked into it”
- **Because:** Behavioral answers need consistent past tense.
- **Trend (recent sessions):** 8 → 4 → 2

## Warm-up drill

_Exercising your recurring pattern: **past tense**._

- ✓ I fixed the crash last week. — **pass**
- ✗ I am fixed the bug. — **fail**
- ✓ I moved the work off the main thread. — **pass**

## Content coverage

_Final-round goal: all STAR components within the time budget._

| Key point | R1 | R3 |
|---|---|---|
| Situation | ✓ | ✓ |
| Task | ✗ | ✓ |
| Action | ✗ | ✓ |
| Result | ✗ | ~ |

**Coverage:** 25% (R1) → 88% (R3), Δ +62%

## Pronunciation flags

_These look like the recognizer mishearing a word you said — practice the pronunciation; they are not grammar mistakes._

- heard **“freeze”** — likely you meant **“frozen”**

## Follow-ups

### Follow-up 1

**Interviewer:** You said the main thread was blocked — how did you confirm that specifically?

**You said:** I read the ANR trace and saw the main thread stuck in a synchronous read.

### Follow-up 2

**Interviewer:** What would you do if it only reproduced on low-end devices?

_No answer — timed out._

## STAR structure check

- **Situation:** ✓ present
- **Task:** ✓ present
- **Action:** ✓ present
- **Result:** ✓ present

## Transcripts

### Attempt 1

So we had a app that freeze on startup and I am look into it.


### Attempt 2

I captured a trace and I found the main thread was blocked on disk IO.


### Attempt 3

I moved the work to a background dispatcher and ANRs dropped to near zero.
