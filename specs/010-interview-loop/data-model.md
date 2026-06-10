# Phase 1 Data Model: Interview Loop

Entities below extend the existing dataclasses. **Convention**: every new field is **additive and
optional** with a default, so frozen dataclasses (`asr.Transcript`, `feedback.frontmatter.*`) and all
existing call sites keep working, and old reports parse unchanged (`schema_version` stays 1, R7). Types
are Python types; "frontmatter" = serialized into the report YAML; "body-only" = rendered into the report
body and not serialized (like attempt transcripts and `coaching`).

---

## 1. Question (extend `content/schema.py:Question`)

| Field | Type | Notes |
|---|---|---|
| `type` | `Literal["definition","behavioral","hypothetical"]` = `"definition"` | NEW. Additive optional question-bank field; absent → `definition` (FR-030). Loader's `_KNOWN_FIELDS` adds `type`; **question-file `schema_version` is NOT bumped** (it stays 1; the report `schema_version` is a separate counter). |

Validation: `type` ∈ the three literals, else a warning and fallback to `definition` (mirrors the existing
`difficulty` validation in `schema.parse`). All other Question fields unchanged.

---

## 2. ASR Transcript (extend `asr/interface.py`)

`WordTiming` (frozen) gains:

| Field | Type | Notes |
|---|---|---|
| `probability` | `float \| None` = `None` | NEW. Per-word confidence from mlx-whisper (`result[...]['words'][j]['probability']`, currently discarded). `None` for Parakeet. |

`Transcript` (frozen) gains:

| Field | Type | Notes |
|---|---|---|
| `segments` | `tuple[SegmentMeta, ...]` = `()` | NEW. Per-segment decode signals. Empty for Parakeet. |
| `vad_regions` | `tuple[SpeechRegion, ...]` = `()` | NEW. Silero speech regions when VAD ran; empty otherwise. |

`SegmentMeta` (new frozen dataclass in `asr/interface.py`):

| Field | Type | Notes |
|---|---|---|
| `start_seconds` | `float` | segment start |
| `end_seconds` | `float` | segment end |
| `text` | `str` | segment text |
| `avg_logprob` | `float \| None` | mlx-whisper segment field |
| `no_speech_prob` | `float \| None` | mlx-whisper segment field |
| `compression_ratio` | `float \| None` | mlx-whisper segment field |

`SpeechRegion` already exists (`vad.py:38-43`: `start_seconds`, `end_seconds`).

---

## 3. Triage result (new, `triage/`)

`SpanClass = Literal["real","mishearing","hallucination"]`.

`TriagedSpan`:

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | the span text |
| `start_seconds` / `end_seconds` | `float` | timing |
| `span_class` | `SpanClass` | `hallucination` → excluded from all analysis/metrics (FR-025); `mishearing` → pronunciation flag (FR-026); `real` → kept |
| `signal` | `str` | why (e.g. `"vad_silence"`, `"no_speech_prob=0.81"`, `"phantom_phrase"`, `"llm_mishearing"`) — for the report and tests |
| `heard` / `likely_intended` | `str \| None` | mishearing only: what was transcribed vs the plausible word |

`TriageResult`: `real_text: str` (concatenated real spans, fed to grammar/coverage), `pronunciation_flags:
list[TriagedSpan]`, `dropped: list[TriagedSpan]` (hallucinations), `real_regions: tuple[SpeechRegion,...]`
(passed to `metrics.compute_all(..., vad_regions=...)`, R8).

---

## 4. Key points & coverage (new, `coverage/`)

`KeyPoint`: `id: int` (1..N stable index), `text: str` (atomic assertion). For behavioral questions the
N=4 points are the STAR components (`Situation/Task/Action/Result`); for definition/hypothetical N∈[5,7]
(FR-018/FR-033).

`KeyPointSet`: `question_id: str`, `ideal_answer_hash: str` (sha256 of normalized ideal answer, R3),
`key_points_version: int` (monotonic, human-facing), `question_type: str`, `points: list[KeyPoint]`.

`CoverageState = Literal["covered","partial","missed"]` (defined operationally in spec Key Definitions).

`KeyPointCoverage`: `key_point_id: int`, `state: CoverageState`.

`CoverageRecord` (per attempt): `attempt_ordinal: int`, `key_points_version: int`, `per_point:
list[KeyPointCoverage]`, `aggregate: float` (= (covered + 0.5·partial)/N). Round-over-round delta and
first-vs-final visibility (FR-020/SC-009) are derived from the per-attempt records (no separate stored
field). Comparisons are only valid within one `key_points_version` (FR-023).

`ContentError`: `attempt_ordinal: int`, `learner_claim: str`, `ideal_claim: str`, `key_point_id: int \|
None`. A mutually-exclusive contradiction only (FR-021); omissions/extra-correct facts are not errors.

---

## 5. Follow-ups (new, `interviewer/` + `feedback/frontmatter.py`)

`FollowUp` (becomes a `Session.follow_ups` entry):

| Field | Type | Notes |
|---|---|---|
| `index` | `int` | 1 or 2 |
| `question_text` | `str` | the unscripted, spoken follow-up (grounded in attempt transcripts) |
| `probe_ref` | `str` | the learner word or `missed` key point it probes (SC-010 evidence) |
| `answered` | `bool` | False on timeout/skip (FR-003/FR-002a) |
| `transcript` | `str` | body-only (like attempt transcripts); empty if unanswered |
| `metrics` | `AttemptMetrics` | fluency over the follow-up answer (FR-004) |
| `grammar_patterns` | `list[GrammarPattern]` | follow-up grammar (aggregated into trends, tagged as follow-up, FR-036) |
| `pronunciation_flags` | `list[TriagedSpan]` | when P4 present |

**No coverage** is scored for follow-ups (no key points — FR-004; resolves the spec's earlier
contradiction).

---

## 6. Warm-up (new, `warmup/` + `feedback/frontmatter.py`)

`DrillItem`: `index: int`, `target_sentence: str`, `target_pattern: str` (the recurring-error label being
exercised), `corrected_form: str`, `error_form: str`.

`DrillItemResult`: `item: DrillItem`, `result: Literal["pass","fail","incomplete"]`, `transcript: str`
(body-only). Pass/fail is **deterministic** (`corrected_form` present and `error_form` absent in the
transcribed response; empty/garbage/silent → `incomplete`) — no LLM at judge time (FR-016 / Key
Definitions).

`Warmup` (becomes `Session.warmup`): `target_pattern: str \| None`, `items: list[DrillItemResult]`,
`skipped_reason: str \| None` (e.g. `"no_recurring_error"`, `"generation_unavailable"`).

---

## 7. Answer-Quality Grade (new, `srs/grade.py`)

`Grade = Literal["poor","fair","good","strong"]`.

`grade_session(coverage: CoverageRecord | None, content_errors: list[ContentError], grammar:
list[GrammarPattern], fluency: AttemptMetrics) -> Grade`:
- **coverage-primary** when `coverage` present: bands on `aggregate` (poor < 0.50 or any content error;
  fair 0.50–0.74; good 0.75–0.94; strong ≥ 0.95 & no content errors & low grammar severity).
- **fallback** when `coverage is None` (P3 absent or analysis pending): grade from grammar severity +
  fluency only (FR-010), so P2 scheduling works before P3 ships.

---

## 8. SRS schedule & mastery (new, `srs/` + store)

`ScheduleEntry` (one per question, lives in the store):

| Field | Type | Notes |
|---|---|---|
| `question_id` | `str` | key |
| `last_grade` | `Grade \| None` | most recent |
| `interval_days` | `int` | current interval (base 1, cap 21 pre-mastery, 30 maintenance) |
| `next_due` | `date` | scheduling output |
| `consecutive_strong` | `int` | for mastery (2 → mastered) |
| `mastered` | `bool` | excluded from active queue (FR-013a) |
| `last_practiced` | `date \| None` | tie-break + history |
| `total_reviews` | `int` | bookkeeping |

**State transitions** (`srs/schedule.py`, R1):
```
new question            → next_due = today (due now), interval = base(1), ranked after overdue (FR-014)
grade poor              → interval = 1;  consecutive_strong = 0; next_due = today + 1
grade fair              → interval = 2;  consecutive_strong = 0; next_due = today + 2
grade good              → interval = min(prev*2, 21);  consecutive_strong = 0; next_due = today + interval
grade strong            → interval = min(prev*2.5, 21); consecutive_strong += 1; next_due = today + interval
consecutive_strong ≥ 2  → mastered = True; interval = 30; next_due = today + 30 (single maintenance review)
maintenance graded <strong → mastered = False; demote into normal rotation per the grade row above
analysis_pending        → entry UNCHANGED (un-graded; stays due, never counts as well-answered, FR-035a)
```

`DueItem`: `question_id`, `next_due`, `last_grade`, `days_overdue`. **Priority order** (FR-012/Key
Definitions): `days_overdue` desc → lower `last_grade` → older `last_practiced`; new (no-history) ranked
after overdue below-mastery items.

---

## 9. Pattern aggregation / trends (extend `trends/` + store)

`PatternTrend`: `label: str`, `series: list[tuple[date, int]]` (occurrence counts over the recent window,
default N=3, chronological, zero-filled for sessions where the pattern did not occur — Key Definitions /
FR-008). Computed from session files (`trends.reader`) and cached in the store; rendered (a) per-pattern
in the session report for patterns found this session **or** seen in the window (FR-008), and (b) across
all questions in the extended `trends` command (FR-009).

---

## 10. Session (extend `feedback/frontmatter.py:Session`)

New **additive optional** fields (serialized to frontmatter unless noted body-only):

| Field | Type | Frontmatter? | Notes |
|---|---|---|---|
| `question_type` | `str` = `"definition"` | yes | mirrors Question.type |
| `warmup` | `Warmup \| None` | yes (transcripts body-only) | P2c |
| `follow_ups` | `list[FollowUp]` | yes (transcripts body-only) | P1 |
| `coverage` | `list[CoverageRecord]` | yes | P3, per attempt |
| `content_errors` | `list[ContentError]` | yes | P3 |
| `pronunciation_flags` | `list[TriagedSpan]` | yes | P4 |
| `key_points` | `KeyPointSet \| None` | yes | P3, the set scored against (incl. hash + version) |
| `answer_grade` | `Grade \| None` | yes | drives SRS |
| `analysis_pending` | `bool` = `False` | yes (only when True) | FR-035/FR-035a; `resume` clears it |
| `triage_summary` | `dict \| None` | yes | counts: real/mishearing/hallucination spans dropped |

Existing fields unchanged. `report_builder.build` gains sections rendered in this order (after the
existing grammar section, mirroring where `coaching` sits): **Warm-up → Coverage (per-attempt +
first/final delta) → Content errors → Pronunciation flags → Follow-ups → type-specific guidance
(STAR / conditional)**, then transcripts. Per-pattern trend lines annotate the existing grammar section.
Sections render only when their data is present; absent → byte-identical to a pre-feature report.

---

## 11. Derived store (new, `store/model.py`)

`Store` (one JSON file, `~/.speakloop/store.json`):

```
{
  "store_version": 1,
  "rebuilt_at": "<iso8601>",
  "schedule":   { "<question_id>": ScheduleEntry, ... },
  "key_points": { "<question_id>": { "<ideal_answer_hash>": KeyPointSet, ... }, ... },
  "patterns":   { "<label>": [ ["<date>", <count>], ... ], ... }
}
```

Invariants: the store is **fully rebuildable** from `data/sessions/*.md` (`store/rebuild.py`); every
field derives from session files (schedule from `answer_grade` + dates; key_points from the latest
session's recorded set; patterns from `grammar_patterns` across reports). `rebuild` overwrites the file
atomically. A missing/corrupt store is rebuilt on next use. The store is a **cache, never a source of
truth** (the session files are).
