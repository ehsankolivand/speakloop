# Feature Specification: Reliable, Higher-Quality Session Feedback

**Feature Branch**: `006-feedback-quality-reliability`

**Created**: 2026-05-22

**Status**: Draft

**Input**: User description: "I want to improve the quality of feedback that users receive in our session reports. Today, when a user finishes a practice session, the report contains grammar suggestions, a narrative summary of how the three attempts progressed, and a single 'top priority for next session' pick. Users sometimes get reports where this analysis is missing, contains malformed sections, or gives suggestions that are inaccurate, unhelpful, or repetitive. The goal of this sprint is to make these existing feedback components reliably higher-quality without adding any new feedback dimensions and without changing which AI model the tool uses."

## Clarifications

### Session 2026-05-22

- Q: How is SC-001's ≤1% failed/unusable-analysis rate verified, given the labeled eval set is only 20–30 cases (where one failure ≈ 3–4%, so a 1% rate is unobservable)? → A: Measure the failure rate over a separate, larger batch of synthetic/replayed sessions (≥100, which need no human labels because failure detection does not); reserve the 20–30 labeled eval set for SC-002 grammar-agreement scoring only.
- Q: Grammar now samples at temperature 0.7, so analyzer output varies run-to-run — how are the pre/post numbers made trustworthy as a verdict? → A: Seed generation where the engine (mlx-lm) allows AND run each case K times (e.g. 3), reporting the median/mean, so a single unlucky sample cannot flip a result.
- Q: What is the exact SC-002 pass bar — "both axes improve" (spec wording) or the precision-weighted F0.5 (scoring contract)? → A: F0.5 MUST clear the pre-registered improvement threshold AND neither precision nor recall may fall below baseline (no regression on either axis).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every finished session yields complete, usable analysis (Priority: P1)

A learner finishes a practice session and reliably receives a complete, well-formed
report. The grammar feedback is present rather than silently degraded to a fluency-only
fallback; no section is malformed, truncated, or garbled; and no suggestion is repeated or
caught in a loop. Under normal operating conditions, the AI analysis essentially never
fails or returns unusable output.

**Why this priority**: The most broadly felt complaint is "the analysis is missing or
malformed." A report that reliably arrives complete and clean is the foundation everything
else rests on — accuracy and trustworthiness improvements cannot even be perceived if the
section is absent or garbled. Hardening reliability is, by itself, a viable, demonstrable
slice of value: reports stop failing and stop showing broken output.

**Independent Test**: Run a representative batch of completed sessions (varied transcript
lengths, including messy L2 speech) and confirm the rate of failed or unusable AI analysis
is at or below the target, that no report contains malformed/truncated/garbled or repeated
output, and that the report structure is identical to today's.

**Acceptance Scenarios**:

1. **Given** a completed session with normal transcripts, **When** the report is generated,
   **Then** the grammar feedback section is present and well-formed — not the degraded
   fluency-only fallback, and not truncated or garbled.
2. **Given** an AI response that is initially malformed (e.g. wrapped in extra text, wrong
   quoting, or partially truncated), **When** the system processes it, **Then** it recovers
   to a usable result, and the report never contains raw or garbled model text.
3. **Given** a long answer, **When** suggestions are produced, **Then** no suggestion or
   fragment is repeated or looped.
4. **Given** a batch of representative sessions under normal operating conditions, **When**
   the failed/unusable-analysis rate is measured, **Then** it is at or below the agreed
   target and noticeably below today's baseline.

---

### User Story 2 - Grammar suggestions are accurate and useful (Priority: P2)

A learner reads grammar suggestions that point at real errors they actually made, propose
corrections that are themselves correct, and explain the issue in plain language. Both
false alarms (flagging things that are not errors) and missed errors drop noticeably from
today's level, and the same issue is never reported twice.

**Why this priority**: This is the heart of the educational value. It is ranked second only
because it depends on User Story 1 — accuracy gains cannot be seen if the section is missing
or malformed — but it is the primary quality lever once output is reliable.

**Independent Test**: On a small held-out set of human-labeled sessions, compare the
AI-identified grammar issues against the human labels before and after the change; confirm
agreement improves on both axes (fewer false alarms, fewer misses). Spot-check a sample to
confirm corrections are grammatically correct and explanations are clear.

**Acceptance Scenarios**:

1. **Given** a transcript containing known L2 errors, **When** grammar analysis runs,
   **Then** each flagged item corresponds to a real error the user actually made, anchored
   to a verbatim, coherent fragment of their own transcript.
2. **Given** a flagged error, **When** the proposed correction is examined, **Then** the
   correction is itself grammatically correct.
3. **Given** a transcript with no error of a given kind, **When** analysis runs, **Then** it
   does not fabricate that error — the false-alarm rate is lower than today's.
4. **Given** a flagged error, **When** the user reads the explanation, **Then** it is plain
   language understandable without grammar jargon.
5. **Given** the same error repeated across attempts, **When** analysis runs, **Then** the
   issue is reported once with the right frequency, not as duplicate entries.

---

### User Story 3 - Narrative and top-priority are trustworthy (Priority: P3)

A learner reads a cross-attempt narrative that is coherent, accurate prose grounded only in
their own transcripts and metrics — it never invents facts that those do not support — and a
single "top priority for next session" that is consistently the most impactful thing to work
on next, rather than a near-random pick from the issue list.

**Why this priority**: Valuable, but it depends on the issue list being reliable (User Story
1) and accurate (User Story 2) first: a top-priority pick can only be meaningful when the
underlying issues are sound, and a narrative can only be trusted when its inputs are. It is
the final polish on a now-reliable, now-accurate report.

**Independent Test**: In a blind review, compare a sample of recent pre-change reports with
post-change reports and confirm reviewers judge the post-change narratives as more accurate
and grounded and the top-priority picks as more meaningful. Separately, verify that no
sentence in a narrative asserts anything unsupported by that report's own transcripts or
metrics.

**Acceptance Scenarios**:

1. **Given** a session's attempts and metrics, **When** the narrative is generated, **Then**
   every claim it makes is supported by the transcripts or the recorded metrics — it states
   no unsupported fact.
2. **Given** a session with several competing issues, **When** the top priority is chosen,
   **Then** it is the single most impactful item by a stable, explainable rule that is
   reproducible from the report itself — not a random or arbitrary selection.
3. **Given** the finished report, **When** it is compared to today's report, **Then** its
   sections, ordering, and structure are unchanged.

---

### Edge Cases

- **Silent or empty transcripts** (no speech captured): the narrative and top-priority
  degrade to the existing sensible defaults, and no grammar errors are fabricated.
- **Mostly-garbled speech-recognition output**: garbled fragments are never cited as grammar
  evidence; if nothing coherent remains, the report says so cleanly rather than rendering a
  malformed section.
- **Model output truncated, looping, fenced, or wrongly quoted**: the system recovers it to a
  usable result or, failing that, uses the existing graceful fallback — it never surfaces raw
  or broken text to the user.
- **A genuinely correct answer with no errors**: the report shows the existing
  "no actionable patterns" outcome rather than inventing errors to fill space.
- **The AI cannot produce usable output even after recovery attempts** (outside normal
  operating conditions, e.g. missing model): the existing graceful degradation and its
  diagnostic note are used; the session does not crash and the report is not corrupted.
- **The same error appears in all three attempts**: it is reported once with an accurate
  occurrence count, not as three duplicate entries.

## Requirements *(mandatory)*

### Functional Requirements

**Reliability of the AI analysis (User Story 1)**

- **FR-001**: Under normal operating conditions, the system MUST produce a complete,
  well-formed report with the AI-derived grammar feedback present (not silently degraded) for
  all but a measurably small, agreed target fraction of sessions.
- **FR-002**: The report MUST never contain raw, garbled, truncated, looping, or repeated
  model text; any such output MUST be recovered to a usable result or handled by the existing
  graceful fallback before the report is written.
- **FR-003**: When usable analysis cannot be produced even after recovery attempts, the system
  MUST degrade gracefully exactly as today — preserving the existing fallback report and its
  diagnostic record — without crashing the session or corrupting the report file.
- **FR-004**: The system MUST not present repeated or near-duplicate restatements of the same
  issue.

**Grammar suggestion quality (User Story 2)**

- **FR-005**: Grammar suggestions MUST identify real errors actually present in the user's
  transcripts; the false-alarm rate (flagging non-errors) MUST drop noticeably from today's
  level.
- **FR-006**: The system MUST reduce the rate of missed real errors compared to today's level.
- **FR-007**: Each suggested correction MUST itself be grammatically correct.
- **FR-008**: Each suggestion MUST carry a plain-language explanation understandable without
  grammar jargon.
- **FR-009**: Every cited error MUST be anchored to a verbatim, coherent fragment of the user's
  own transcript; garbled speech-recognition fragments MUST NOT be cited (preserving today's
  verbatim-evidence and coherence guarantees).
- **FR-010**: A "correction" identical to the original (a no-op fix) MUST NOT be presented.

**Narrative and top-priority quality (User Story 3)**

- **FR-011**: The cross-attempt narrative MUST be coherent, accurate prose grounded solely in
  the session's transcripts and recorded metrics; it MUST NOT assert facts those do not
  support.
- **FR-012**: The "top priority for next session" MUST be the single most impactful item,
  selected by a stable, explainable, reproducible rule, drawn only from the session's own
  issues and metrics — never an arbitrary or near-random pick.
- **FR-013**: The narrative and top-priority MUST degrade to the existing sensible defaults
  when no speech or no actionable pattern is present.

**Format, scope, and platform constraints (all stories)**

- **FR-014**: The report format, sections, ordering, and structure MUST remain identical to
  today's; no new section is added and the improvements MUST be invisible to the user as a
  format change.
- **FR-015**: No new feedback dimension may be added. Comparing the user's answer to an ideal
  answer (semantic-equivalence judging) is explicitly out of scope for this sprint.
- **FR-016**: All processing MUST remain fully offline; no new external service or network call
  may be introduced.
- **FR-017**: The AI model used by the tool MUST stay the same; no model swap.
- **FR-018**: No change may bump the report's persisted schema version or break existing saved
  reports or cross-session trends; any internal data additions MUST remain backward-compatible.
- **FR-019**: The project's governing principles MUST be preserved: offline-first operation,
  English-only user-facing output, modular boundaries, and the single-wrapper, swappable-engine
  arrangement for the AI model.

**Verifiability (supports the success criteria)**

- **FR-020**: The team MUST be able to measure, before and after the change and by a repeatable
  offline method, (a) the rate of failed or unusable AI analysis — over a larger batch of
  synthetic/replayed sessions (≥100, no human labels required) so a ~1% rate is observable — and
  (b) the agreement between AI-identified grammar issues and a small (20–30 case) held-out
  human-labeled set. Because grammar generation is stochastic (temperature 0.7), the method MUST
  seed generation where the engine allows and repeat each case (e.g. 3 runs), reporting the
  median/mean so a single sample cannot flip a verdict. This measurement capability is a
  validation activity, not an end-user-facing feature.

### Key Entities *(include if feature involves data)*

- **Session report**: The document a learner reads after a session. Structure is unchanged;
  it contains the grammar suggestions, the cross-attempt narrative, and the single
  top-priority pick.
- **Grammar suggestion**: A detected error with verbatim evidence from the user's transcript,
  a grammatically correct proposed correction, and a plain-language explanation; ordered by
  impact.
- **Cross-attempt narrative**: Prose describing how the attempts progressed, grounded only in
  the session's transcripts and metrics.
- **Top-priority pick**: The single most impactful next focus, chosen by a stable, explainable
  rule from the session's own issues and metrics.
- **Held-out evaluation set**: A small set of human-labeled sessions used only to measure
  grammar-suggestion agreement before and after the change. A validation artifact, not shipped
  to users.
- **Degradation record**: The existing mechanism that records when usable analysis could not be
  produced and the report fell back; retained as the safety net.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The rate of sessions with failed or unusable AI analysis drops from the measured
  baseline to at most 1% of sessions under normal operating conditions. Because a 20–30 case
  labeled set is too small to observe a 1% rate, this rate is measured over a separate, larger
  batch of synthetic/replayed sessions (≥100, which need no human labels); the 20–30 labeled eval
  set is used only for SC-002.
- **SC-002**: Agreement between AI-identified grammar issues and the held-out human-labeled set
  improves measurably after the change versus before, on both axes — fewer false alarms and
  fewer missed errors. Concretely, the precision-weighted F0.5 MUST clear the pre-registered
  improvement threshold (set when the baseline is captured) AND neither precision nor recall may
  fall below baseline — no regression on either axis.
- **SC-003**: In a blind paired review of recent pre-change reports versus post-change reports,
  reviewers judge the post-change narrative as more accurate and grounded, and the top-priority
  pick as more meaningful, in a clear majority of pairs.
- **SC-004**: Across a measured batch, zero reports contain raw, garbled, looping, or malformed
  output, and zero contain duplicated suggestions.
- **SC-005**: The report format, sections, and structure are unchanged from today and the
  report's persisted schema version is unchanged, confirmed by existing report/format checks
  continuing to pass.
- **SC-006**: No network activity occurs during analysis and the same AI model is used — the
  offline guarantee and the no-model-swap constraint both hold.
- **SC-007**: In a sampled review of post-change reports, every examined correction is
  grammatically correct and every examined explanation is plain language.

## Assumptions

- **"Normal operating conditions"** means the AI model is present and loadable and the session
  has at least one non-silent attempt with intelligible speech. Pathological inputs — all-silent
  sessions, fully-garbled speech recognition, or a missing/unloadable model — are excluded from
  the failure-rate target (SC-001) and continue to be handled by the existing graceful fallbacks.
- The **target failure rate** is operationalized as "near zero" → at most 1% under normal
  conditions; the precise target is confirmable during planning once the current baseline is
  measured. ("Today's level" is captured as a baseline before any change.)
- The **mechanism** for each component (deterministic, model-assisted, or a hybrid) is a planning
  decision. The binding requirements here are the outcomes (reliability, accuracy, grounding) and
  the constraints (offline, same model, identical format, no new dimension). The technical
  research at `doc/QWEN_IMPROVMENT_RESEARCH.md` is the source of truth for configuration,
  prompt-design, and output-recovery decisions made during planning.
- The **existing graceful-degradation path** (and its diagnostic record) is retained as the
  safety net. This sprint reduces how often it triggers; it does not redesign it.
- The **grammar error catalog** content is reused as-is. Quality gains come from configuration,
  prompting, and output-recovery, plus the existing verification logic (verbatim-evidence and
  coherence guarantees) — curating or expanding the catalog is not required by this sprint.
- A **larger unlabeled batch of synthetic/replayed sessions** (≥100, for the SC-001 failure
  rate), a **small (20–30 case) held-out human-labeled evaluation set** (for SC-002 agreement),
  and a **repeatable offline measurement / replay method** (seeded where supported, multi-run
  median to absorb temperature-0.7 sampling variance) are created as part of validating this
  sprint; none ships as an end-user feature.
- No new third-party dependency is assumed necessary; if planning identifies one as the only
  viable path for output recovery, it is flagged for explicit decision rather than assumed in.
- Supported platform remains macOS Apple Silicon with the existing toolchain, consistent with
  prior features.
- This sprint explicitly stays on the 4-bit model variant (`mlx-community/Qwen3-8B-4bit`); evaluating
  or adopting the 8-bit variant is out of scope, because the additional ~4 GB download is a real
  per-user bandwidth cost in the target deployment region (Constitution VI, VII).
