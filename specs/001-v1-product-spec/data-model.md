# Data Model — speakloop v1

This document defines the entities, their fields, relationships, and the versioned schemas the system reads and writes. It is technology-agnostic enough that an alternate implementation could honor it; concrete Python types are documented in `contracts/`.

## Entity overview

```text
Question ──< (in) Q&A File
   │
   └──< (drives) Practice Session
                       │
                       ├── Attempt #1   ─┐
                       ├── Attempt #2   ─┼── feed Metrics + Grammar Analysis
                       └── Attempt #3   ─┘
                       │
                       └── produces ─→ Session Report (Markdown file)
                                              │
                                              └──< (aggregated by) Trends Summary
```

---

## 1. Question

A single interview prompt the user practices.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | string, kebab-case, ≤ 40 chars | yes | Stable identifier; matches `qXX` token in report filenames after normalization. Examples: `kotlin-coroutines-basics`, `system-design-rate-limiter`. |
| `question` | string, 1..1000 chars | yes | The interview question, spoken aloud verbatim. |
| `ideal_answer` | string, 1..4000 chars | yes | The ideal answer, spoken aloud verbatim. |
| `tags` | list of strings | no | E.g. `[behavioral, system-design]`. Used for filtering in future versions; v1 ignores them. |
| `difficulty` | enum `easy`|`medium`|`hard` | no | Display-only; v1 does not branch on this. |
| `voice_override` | string | no | Optional Kokoro voice name (e.g. `bm_george`). Default voice picked at module load. |

**Validation rules**:

- `id` must be unique across the file.
- `question` and `ideal_answer` must be non-empty after trimming.
- Unknown keys are surfaced as warnings (not errors) so the schema can evolve forward-compatibly.

**Source of truth**: the user's YAML file at `~/.speakloop/qa.yaml`. A starter file is committed at `src/speakloop/content/starter.yaml` and copied on first run if no user file exists.

---

## 2. Q&A File

The YAML document that holds Questions.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | int | yes | Currently `1`. |
| `questions` | list of Question | yes | At least one entry. |

See `contracts/content-schema.yaml` for the canonical schema.

---

## 3. Practice Session

A single execution of the 4/3/2 loop for one Question. Lives only in memory while the session runs; persisted only via the **Session Report** below.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `started_at` | ISO 8601 datetime, local tz | wall clock at session start | Frontmatter only. |
| `question_id` | string | from selected Question | Echoed into filename. |
| `question_text` | string | from selected Question | Echoed into frontmatter so the report is self-contained even after the YAML is edited. |
| `attempts` | list of Attempt, length 3 | runtime | One per round. |
| `completed` | bool | runtime | False if Ctrl+C; in that case no report is written (FR-016). |

**State transitions**: `not_started → listening → attempt_1 → attempt_2 → attempt_3 → analyzing → reporting → done`. A signal at any state up to and including `reporting` aborts cleanly without writing a report.

---

## 4. Attempt

One recorded answer within a session.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `ordinal` | int 1..3 | yes | Round number. |
| `time_budget_seconds` | int | yes | 240, 180, or 120 — derived from `ordinal`. |
| `actual_duration_seconds` | float | yes | Wall-clock duration of the recording. |
| `transcript` | string | yes | ASR-produced; may be empty if the user stayed silent. |
| `metrics` | Fluency Metric set | yes | See entity 5. |

**Privacy note**: the raw recorded audio file MAY be deleted after transcription per Spec Assumption "Recorded audio is transient by default." The transcript is the persisted truth. Retention policy is a Phase B implementation decision; data model does not require keeping the WAV.

---

## 5. Fluency Metric set (per Attempt)

A fixed-shape record computed from the transcript and the recorded duration. The **shape** is fixed in v1; the **numeric thresholds and definitions** are sourced from `doc/research_methodology.md` (currently unauthored — see plan.md § Complexity Tracking).

| Field | Type | Units | Notes |
|-------|------|-------|-------|
| `words_total` | int | count | After tokenization; excludes pure punctuation. |
| `speech_rate_wpm` | float | words/min | `words_total / (actual_duration_seconds / 60)`. |
| `filler_words_count` | int | count | Configurable list: `uh`, `um`, `like`, `you know`, … Methodology doc to finalize the list. |
| `filler_density_per_100_words` | float | per 100 words | `filler_words_count / words_total * 100`. |
| `pauses_count` | int | count | A pause is any non-speech segment ≥ 250 ms (FR-012b, matching the MLR threshold cited in `doc/research_methodology.md`). |
| `mean_pause_ms` | float | ms | Average pause duration. |
| `self_corrections_count` | int | count | Heuristic from transcript: false-start tokens / repaired phrases. Methodology doc to refine. |

All metrics are computed identically for the three attempts so the report's cross-attempt comparison (FR-012) is meaningful.

---

## 6. Grammar Pattern Finding

An observation produced by the LLM analyzer in Phase C.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `pattern_label` | string | yes | Short, human-readable: e.g. `missing articles before singular count nouns`. |
| `occurrence_count` | int | yes | How many times the pattern appeared across the three transcripts. |
| `evidence` | list of Evidence Quote | yes, ≥ 1 | Each is a verbatim transcript snippet (FR-013). |
| `suggested_fix` | string | no | Optional one-line correction example. |

### Evidence Quote (sub-entity)

| Field | Type | Notes |
|-------|------|-------|
| `attempt_ordinal` | int 1..3 | Which attempt the quote is from. |
| `quote` | string | Verbatim substring of the attempt's transcript. |

---

## 7. Session Report (Markdown file on disk)

The Markdown artifact under `data/sessions/`.

**Filename**: `YYYY-MM-DD-q<question_id>.md`. If a file with that name already exists (two sessions for the same question on the same day), append `-2`, `-3`, … before `.md` (FR-017).

**Layout**:

```markdown
---
schema_version: 1
session_id: 2026-05-18-kotlin-coroutines-basics
started_at: 2026-05-18T19:14:02-07:00
question_id: kotlin-coroutines-basics
question: |
  Explain how Kotlin coroutines differ from threads.
attempts:
  - ordinal: 1
    time_budget_seconds: 240
    actual_duration_seconds: 213.4
    metrics:
      words_total: 412
      speech_rate_wpm: 115.9
      filler_words_count: 18
      filler_density_per_100_words: 4.4
      pauses_count: 21
      mean_pause_ms: 740
      self_corrections_count: 3
  - ordinal: 2
    time_budget_seconds: 180
    # ...
  - ordinal: 3
    time_budget_seconds: 120
    # ...
grammar_patterns:
  - label: missing articles before singular count nouns
    occurrence_count: 7
  - label: subject-verb agreement on collective nouns
    occurrence_count: 3
generated_by_phase: C   # or "B" for Phase-B-only interim reports
---

# Kotlin coroutines vs threads — 2026-05-18

## Attempt-by-attempt summary

| Round | Budget | Used | WPM | Fillers/100w | Pauses |
|-------|--------|------|-----|--------------|--------|
| 1     | 4:00   | 3:33 | 116 | 4.4          | 21     |
| 2     | 3:00   | 2:58 | 124 | 3.1          | 14     |
| 3     | 3:00   | 2:00 | 138 | 2.0          | 9      |

## Cross-attempt comparison

Your speech rate climbed from 116 to 138 WPM …

## Grammar patterns

### Missing articles before singular count nouns *(7×)*
> "Coroutine is suspendable computation that runs on dispatcher."
> "I would use dispatcher to switch context."
Suggested: "*A* coroutine is *a* suspendable computation that runs on *a* dispatcher."

### …

## Transcripts

### Attempt 1
…verbatim…

### Attempt 2
…

### Attempt 3
…
```

**Frontmatter schema is versioned** (`schema_version: 1`). Future-incompatible changes require a bump and a migration note (Constitution Development Guidelines, "Stable report schema").

**Phase-B interim form**: `grammar_patterns` is `[]` and `generated_by_phase: B`. The Phase-B report is otherwise identical so the trends reader (Phase C) handles both forms.

---

## 8. Trends Summary (in-memory, displayed only)

The trends dashboard does not write a file; it renders to the terminal.

| Field | Type | Source |
|-------|------|--------|
| `total_sessions` | int | count of valid report files |
| `date_range` | (earliest, latest) tuple | from frontmatter `started_at` |
| `metric_series` | dict of metric-name → list of (date, attempt-3 value) | Attempt 3 is used because it is the most-rehearsed attempt and the most directly comparable across sessions. |
| `pattern_ranking` | list of (pattern_label, total_occurrences, list of session_ids) | Top-N (default N=10) sorted descending. |

---

## 9. Model (locally-stored AI model)

Tracked by the installer.

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Display name (`Kokoro-82M`, `Parakeet-TDT-0.6b-v3`, `Qwen3-8B-4bit`). |
| `hf_repo_id` | string | HuggingFace repo for `snapshot_download`. |
| `expected_size_bytes` | int | For consent disclosure and validation. |
| `local_path` | string | Under `~/.speakloop/models/<repo-id-slug>/`. |
| `required_for_phase` | enum `A`|`B`|`C` | TTS=A, ASR=B, LLM=C. The installer consents and downloads only what's needed for the phase the user is in. |

The set of models the installer knows about is the `installer/manifest.py` constant — the only file that needs editing when an engine swap happens at the manifest level (the wrapper file change is separate per Principle V).

---

## Schema versioning

- Q&A file: `schema_version: 1`.
- Session report frontmatter: `schema_version: 1`.

Both bumps require:
1. A migration note in `feedback/frontmatter.py` (for report) or `content/loader.py` (for Q&A).
2. A new fixture under `tests/fixtures/` exercising the bump path.
3. The trends reader must be able to read the previous schema version forever (forward-compat for old user data).
