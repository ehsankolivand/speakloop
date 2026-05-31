# Contract: Report invariance — "nothing the user sees changes"

**Feature**: 006-feedback-quality-reliability · **Phase**: 1 · **Owner module**: `feedback/`

The sprint improves *content quality and reliability*, not the report. This contract is the
guardrail for FR-014, FR-015, FR-018, FR-019 and SC-005/SC-006.

## Invariants (MUST hold byte-for-structure)

- **I1 — Schema version**: `feedback/frontmatter.py` `SCHEMA_VERSION` stays **1**. No bump.
- **I2 — Frontmatter keys**: no key added, removed, renamed, or retyped on the normal path.
  Any future addition is **additive + optional + emitted only when present** (the existing
  `asr:` / `phase_c_error` pattern). 006 sprint added one such key — `ideal_answer:` — under
  this rule: additive, optional, only emitted when the Q&A entry has one (post-2026-05-25).
- **I3 — Sections & order**: the body keeps today's sections and order from
  `report_builder.build()` — (optional Question & reference answer →) Top priority →
  Attempt-by-attempt table → Cross-attempt comparison → Grammar patterns → Transcripts.
  The "Question & reference answer" block is optional and only renders when `ideal_answer`
  is present; no section added or removed on the pre-feature path.
- **I4 — "You said / Better / Because"** card shape and the impact-ranked ordering are unchanged.
- **I5 — Graceful fallback retained**: the Phase-B placeholder, the `NO_PATTERNS_LINE`, and the
  `phase_c_error` ⚠️ note render exactly as today when analysis is unavailable (FR-003). This
  sprint reduces *how often* they appear; it does not restyle them.
- **I6 — English-only** (Principle I): any user-facing string that changes stays English. No
  new locale surface.
- **I7 — No new *feedback* dimension** (FR-015): no semantic-equivalence judging, no scoring,
  no new card type, no new metric. **The Q&A reference answer is a static copy** for the
  human reader (post-2026-05-25), not a feedback dimension: the AI never receives it
  (grammar analyzer takes transcripts only; narrative is deterministic over metrics).

## What MAY change (content, not structure)

- The *values* inside grammar cards (more accurate labels, corrections, explanations; fewer
  false alarms; deduplicated).
- The *wording* of the deterministic cross-attempt narrative — tightened so every clause is
  grounded in the session's transcripts/metrics (FR-011). Still deterministic (see plan
  Decision 1); still no LLM-invented fact.
- The *selection* the deterministic top-priority rule lands on, because its inputs (the issue
  list) get better — the **rule itself stays reproducible** from the report (FR-012).

## Verification

- **V-R1**: existing report/format/golden tests in `tests/` continue to pass unchanged (SC-005).
  If any asserts on exact narrative wording, update the golden text **and** confirm structure is
  untouched — a wording diff is allowed, a structural diff is not.
- **V-R2**: a `dump → parse → dump` round-trip stays idempotent and `schema_version: 1`
  (existing frontmatter guarantee).
- **V-R3**: a pre-feature report and a post-feature *clean* report differ only in grammar/narrative
  **content**, never in key set, section set, or ordering (structural diff = empty).
- **V-R4**: no network call occurs during a full session+analysis (SC-006) — assert via the
  offline guard already used for engine-import isolation.
- **V-R5**: the model is unchanged — `mlx-community/Qwen3-8B-4bit` (family **and** quantization);
  no swap (FR-017 stays absolute — 8-bit is out of scope this sprint, plan Decision 2).
