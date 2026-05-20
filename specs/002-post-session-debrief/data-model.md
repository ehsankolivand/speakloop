# Data Model — Post-Session Interactive Debrief

This feature **extends** the v1 data model (`specs/001-v1-product-spec/data-model.md`)
without breaking it. All persisted changes are **additive** to the existing
`schema_version: 1` report frontmatter (Constitution Principle IX; Development
Guidelines "Stable report schema"). The trends reader, which consumes only
`label` + `occurrence_count` + the attempt metrics, continues to work unchanged
(FR-031).

Entities below are grouped into **persisted** (written to the report file) and
**in-memory** (built for the debrief, never serialized).

---

## A. Persisted entities (additive frontmatter — schema_version stays 1)

### A.1 Grammar Pattern Finding (extended)

Extends v1 data-model §6. New fields are optional and default-empty so older
readers and Phase-B reports are unaffected.

| Field | Type | New? | Notes |
|-------|------|------|-------|
| `label` | string | existing | Now MUST match a catalog `label`/`id`, or be an open-bucket label. |
| `occurrence_count` | int | existing | Unchanged. |
| `evidence` | list of Evidence Quote | existing (extended) | Each item gains an optional `corrected` field — see A.2. |
| `suggested_fix` | string | existing | Retained for backward-compat; superseded by structured `explanation` + per-evidence `corrected`. MAY be omitted in new reports. |
| `explanation` | string | **NEW** | One-line transfer reason for a B1–B2 learner (the "Because:" line). For catalog patterns, sourced from the catalog `transfer_reason`; for open-bucket patterns, provided by the LLM and verified non-empty. |
| `impact_rank` | int | **NEW** | 1 = highest impact on interview comprehensibility. Resolved deterministically at build time (catalog rank for seed patterns; fixed below-catalog default for open-bucket). Persisted so render/read-aloud order is reproducible (FR-005). |
| `catalog_id` | string \| null | **NEW** | The catalog entry id when the pattern is a catalog match; `null`/absent for open-bucket patterns. |

**Validation rules**:
- Every reported pattern has ≥ 1 coherent verbatim evidence item after the
  coherence filter (FR-006/FR-007); patterns with none are dropped.
- `explanation` is non-empty for every reported pattern.
- A pattern whose only correction equals the original quote is suppressed (FR-009).
- Open-bucket patterns require `occurrence_count >= 2` (unchanged FR-002).

### A.2 Evidence Quote (extended)

Extends v1 data-model §6 sub-entity. The `quote` is the user's verbatim words
(the "You said:" line); the new `corrected` is the rewrite (the "Better:" line).

| Field | Type | New? | Notes |
|-------|------|------|-------|
| `attempt_ordinal` | int 1..3 | existing | Which attempt the quote is from. |
| `quote` | string | existing | Verbatim substring of that attempt's transcript (FR-007). Survives the coherence filter (FR-006). |
| `corrected` | string | **NEW** | The corrected version of `quote` (the "Better:" line). Optional but expected; ≥ 80% of fixes carry it (SC-003). MUST differ from `quote` (FR-009). |

### A.3 Session Report frontmatter (extended)

Two new top-level keys, both additive; everything else in v1 §7 is unchanged.

| Field | Type | New? | Notes |
|-------|------|------|-------|
| `schema_version` | int | existing | **Stays `1`.** Changes here are additive only. |
| `cross_attempt_narrative` | string | **NEW** | Deterministic prose: what improved across 4/3/2, what stayed the same (FR-008). Block scalar. |
| `top_priority` | string | **NEW** | The single most important thing to fix next session (FR-008). Derived deterministically by a **most-impactful-wins** rule: the highest-impact item across grammar patterns (scored by `impact_rank`) and fluency dimensions (scored by a fixed severity heuristic) — a fluency issue may win even when grammar patterns exist. Degrades to a sensible default when neither is notable. |
| `generated_by_phase` | "A"\|"B"\|"C" | existing | Unchanged. Phase-B reports may carry `cross_attempt_narrative`/`top_priority` (fluency-only) but `grammar_patterns: []`. |

**Migration note**: none required — additive fields. A reader of the previous
shape ignores unknown keys; the trends reader is unaffected (it reads `label`,
`occurrence_count`, `attempts[].metrics`). New fixtures under `tests/fixtures/`
exercise the additive round-trip (Development Guidelines).

---

## B. Persian-L1 Error Catalog (new in-repo data file)

`src/speakloop/feedback/persian_l1_catalog.yaml`, loaded once by
`feedback/catalog.py` into frozen dataclasses. Schema in
`contracts/persian-l1-catalog.yaml`.

### B.1 Catalog Entry

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | string, kebab-case | yes | Stable id, e.g. `gerund-infinitive-confusion`, `comparative-form`, `plural-agreement`, `article-omission-common`, `3sg-s-drop`, `aux-drop`, `preposition-substitution`, `possessor-order`. |
| `label` | string | yes | Human-readable label shown in the report. |
| `transfer_reason` | string | yes | One-line B1–B2 explanation of why the error happens (the "Because:" line for catalog patterns). |
| `impact_rank` | int | yes | Impact weight derived from `doc/research_methodology.md` §1.1 (1 = highest). |
| `detection_hints` | list of string | yes | Short cues injected into the LLM prompt to anchor accurate labelling. |
| `examples` | list of {wrong, right} | yes | Seed wrong→right pairs (also used in tests). |
| `methodology_ref` | string | yes | Pointer to the methodology pattern number/section this entry derives from (Principle X traceability). |

### B.2 Catalog (file)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `catalog_version` | int | yes | Independent of report `schema_version`; lets the catalog evolve. Currently `1`. |
| `entries` | list of Catalog Entry | yes | The seed set; ≥ the documented Persian-L1 categories. |

**Open-bucket rule**: patterns the LLM surfaces that match no `id`/`label` are
admitted as open-bucket findings with a fixed default `impact_rank` placing them
below all catalog patterns, subject to `occurrence_count >= 2` (FR-002
preserved).

---

## C. In-memory entities (debrief; never serialized)

Built by `debrief/view_model.py` from the in-memory `Session` returned by
`run_session`. The report file remains the only on-disk artifact.

### C.1 DebriefViewModel

| Field | Type | Notes |
|-------|------|-------|
| `is_first_time` | bool | True when no prior report exists in `sessions_dir` (excluding the just-written one) → shows the orientation line (FR-030). |
| `top_priority` | string | From frontmatter `top_priority` (most-impactful-wins; may be grammar or fluency). Rendered as the bordered banner (FR-011). |
| `narrative` | string | From `cross_attempt_narrative`. Audio-eligible (FR-017). |
| `attempt_rows` | list of AttemptRow | For the trend-coloured summary table (FR-013). |
| `pattern_cards` | list of PatternCard | Ranked by `impact_rank` (FR-005); each rendered as a three-line card (FR-012). |
| `transcript_previews` | list of TranscriptPreview | Collapsed by default (FR-014). |
| `transcripts_expanded` | bool | Toggle state driven by the menu `t` key (FR-014/FR-024); `False` (collapsed) on entry and reset to `False` on replay. When `True`, previews render full text in place. |
| `grammar_available` | bool | False when the LLM model is absent → grammar section replaced by the one-line placeholder (FR-028). |
| `audio_sections` | list of AudioSection | Ordered narrative → top priority → each pattern (FR-018); drives "X of N" (FR-019). |

### C.2 AttemptRow

| Field | Type | Notes |
|-------|------|-------|
| `ordinal` | int 1..3 | Round. |
| `budget` / `used` | string mm:ss | Time budget vs used. |
| `wpm` | float | With `wpm_trend`. |
| `filler_density` | float | With `filler_trend`. |
| `pauses` | int | Display only. |
| `wpm_trend` / `filler_trend` | enum `improved`\|`flat`\|`worsened` | Computed by comparing first vs last attempt with a small tolerance band (Assumptions); maps to green/yellow/red (FR-013). For WPM, higher is "improved"; for filler density, lower is "improved". |

### C.3 PatternCard

| Field | Type | Notes |
|-------|------|-------|
| `label` | string | Card title. |
| `impact_rank` | int | Sort key. |
| `you_said` | string | First evidence `quote` (the primary example). |
| `better` | string | Matching `corrected`. |
| `because` | string | The pattern `explanation`. |
| `extra_evidence` | list of (quote, corrected) | Additional examples, shown beneath the primary three lines. |

### C.4 TranscriptPreview

| Field | Type | Notes |
|-------|------|-------|
| `ordinal` | int 1..3 | Round. |
| `preview` | string | First ~10 words. |
| `remaining_words` | int | For the "+143 words" indicator (FR-014). |
| `full_text` | string | Shown only when the user expands explicitly. |

### C.5 AudioSection

| Field | Type | Notes |
|-------|------|-------|
| `kind` | enum `narrative`\|`top_priority`\|`pattern` | Determines order and highlight target. |
| `index` | int | Position in the read-aloud sequence (for "X of N"). |
| `speak_text` | string | The text synthesized aloud. For a pattern: its `explanation` + the corrected version (FR-017). Transcripts and raw metrics are never included (FR-017). |
| `highlight_ref` | renderable id | Which on-screen section to highlight while this plays (FR-019). |

### C.6 DebriefChoice

| Field | Type | Notes |
|-------|------|-------|
| `value` | enum `replay`\|`new`\|`quit` | The user's terminal menu selection (FR-023/FR-024) driving the practice-loop control flow. |

The transcript-toggle key `t` (FR-014/FR-024) is **not** a `DebriefChoice`: it
flips `DebriefViewModel.transcripts_expanded` and re-renders in place, keeping the
menu open. The menu loop consumes `t` internally and only returns once one of
`replay`/`new`/`quit` is chosen.

---

## D. Coordinator result (in-memory, additive)

`sessions/coordinator.run_session(...)` currently returns the report `Path`. It
will return both the path and the in-memory `Session` so the debrief renders from
typed data without re-parsing the Markdown file.

| Field | Type | Notes |
|-------|------|-------|
| `report_path` | Path | As today. |
| `session` | frontmatter.Session | The fully-populated session (attempts, grammar_patterns, narrative, top_priority, phase). |

This is an internal return-shape change (not part of any persisted schema or
engine Protocol); call sites (`cli/practice.py`, tests) update accordingly.

---

## Schema versioning

- Report frontmatter: **`schema_version: 1` unchanged** — all changes additive.
- Q&A file: unchanged.
- Catalog file: introduces its own independent `catalog_version: 1`.
- The trends reader MUST continue to read both pre-feature and post-feature
  reports (forward-compat for old user data) — guaranteed because no existing
  field changed meaning or shape.
