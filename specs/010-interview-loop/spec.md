# Feature Specification: Interview Loop

**Feature Branch**: `010-interview-loop`

**Created**: 2026-06-10

**Status**: Draft

**Input**: User description: "Extend SpeakLoop with an 'Interview Loop' feature set that turns isolated practice sessions into an adaptive training loop — interactive follow-up questions, cross-session memory and spaced-repetition scheduling, content-coverage scoring, a trustworthy feedback triage pipeline, and behavioral/hypothetical question types."

## Overview

Today the learner practices one question in isolation: the tool plays a question and an ideal answer, records three timed spoken attempts (4 / 3 / 2 minutes), transcribes them, and writes a per-session report with fluency metrics and grammar-pattern feedback. The report is excellent but disposable — its lessons don't follow the learner into the next session, the practice is a monologue (real interviews are interactive), and the feedback grades *how* the learner spoke but not *whether what they said was correct or complete*.

This feature closes those three gaps and hardens the pipeline against wrong feedback. It is built for one concrete learner — a Persian-speaking Android developer preparing for English-language technical interviews on a ~3.5-month runway — and turns the existing one-shot session into a repeatable daily training loop:

> **due-question selection → warm-up drill → question + 3 attempts → 1–2 spoken follow-ups → report (with coverage, content errors, pronunciation flags, and cross-session trends)**

The work ships in five prioritized, independently valuable slices (P1 highest). Each slice is a complete, demonstrable improvement on its own; together they form the loop.

All existing constraints continue to hold: the tool is a CLI (no GUI), English-only in its user-facing output, offline-first by default (the only network use is the existing opt-in cloud-analysis mode and the one-time model download), and every session report stays a portable, human-readable report file that opens in common note-taking tools. Existing reports remain backward-compatible: all new report data is additive and optional, and a report that lacks it still opens and displays correctly.

### Slice independence & sequencing

The five stories are prioritized but **each must be shippable on its own** against today's system. To keep that true, every slice reuses only (a) what already exists today and (b) what is internal to that slice. Where a later slice would enrich an earlier one (e.g., triage from P4 cleaning follow-up answers in P1, or content coverage from P3 informing the answer-quality grade in P2), the earlier slice MUST define a self-contained fallback that works without the later slice, and the enrichment is applied **only when the later slice is present**. The cross-slice fallbacks are stated explicitly in the requirements (FR-004, FR-010, FR-016).

## Clarifications

### Session 2026-06-10

Resolved by the spec author across three areas (interviewer interaction, spaced-repetition policy, warm-up format), confirming existing defaults where one was already stated and pinning the few open values. Each answer is integrated into the sections noted in parentheses.

- Q: Can the learner replay or skip a spoken follow-up, and what happens on silence? → A: The learner may replay a follow-up **once** on demand (does not consume the answer budget) and may **skip** it; total silence within the budget is still recorded as an unanswered timeout. (FR-002a, US1 scenario 5, Edge Cases)
- Q: What is the default spaced-repetition interval scheme? → A: Base interval 1 day; **poor → 1 day (reset to base); fair → 2 days; good → previous × 2; strong → previous × 2.5**, capped at 21 days until mastery. (Key Definitions — Spaced-repetition interval ladder; FR-011)
- Q: What counts as "answered poorly" (the 1–2-day resurfacing trigger)? → A: A session graded **poor** = aggregate coverage < 0.50 **or** any content error → resurfaces in 1 day; a **fair** grade (coverage 0.50–0.74, no content error) → 2 days. (Key Definitions — Answer-Quality Grade; FR-011)
- Q: What is the definition of mastery, and what happens to a mastered question? → A: **Two consecutive 'strong' grades with zero content errors.** A mastered question leaves the active due queue but is not retired — it returns for a single maintenance review at the 30-day ceiling, and any later non-'strong' result demotes it back below mastery and into rotation. (Key Definitions — Mastery; FR-013a)
- Q: What is the warm-up drill format and how is pass/fail judged? → A: **Three drill items**, each one target sentence exercising the corrected form of the top recurring error, 30–60 s total; **pass** = transcribed response contains the corrected form and not the error form, **fail** = it does not, **incomplete** = empty/garbage/silent (not a fail). (Key Definitions — Warm-up drill item; FR-016)

## Key Definitions

These operational definitions make the requirements and success criteria testable. Concrete default numbers are starting values the learner or planning may tune; they are stated so a tester has a falsifiable target, not to prescribe an algorithm.

- **Answer-Quality Grade**: a per-question, per-session band — **poor / fair / good / strong** — assigned from the analysis available that session. Primary signal is content coverage (P3); when coverage is unavailable (P3 not active, or analysis could not run), the grade falls back to grammar severity + fluency only. Default coverage-based bands: **poor** = aggregate coverage < 0.50 **or** any content error; **fair** = 0.50–0.74 and no content error; **good** = 0.75–0.94 and no content error; **strong** = ≥ 0.95 with no content errors and low grammar severity. "Answered poorly" means a **poor** grade. The grade drives scheduling.
- **Spaced-repetition interval ladder**: the next-due interval is derived from the grade against the question's previous interval (base = 1 day): **poor** → 1 day (reset to base); **fair** → 2 days; **good** → previous × 2; **strong** → previous × 2.5. Intervals are capped at 21 days until the question is mastered. Poor (1 day) and fair (2 days) together realize the request's "resurface within 1–2 days."
- **Mastery**: a question is *mastered* when its two most recent reviews were both graded **strong** with zero content errors. A mastered question leaves the active due queue but is not retired: it returns for a single **maintenance review** at the 30-day ceiling, and any later non-**strong** result demotes it below mastery and back into normal rotation. Until mastered, a question stays in rotation.
- **Coverage state** (per key point, per attempt): **covered** = the key point's core assertion is stated correctly; **partial** = the topic is mentioned but the assertion is incomplete, hedged, or only half-right; **missed** = not mentioned, or contradicted. Aggregate coverage for an attempt = (covered + ½·partial) ÷ number of key points.
- **Content error**: a learner statement that asserts a claim about a topic that is *mutually exclusive* with what the ideal answer asserts about that same topic (e.g., learner "Android 11" where the ideal answer says "Android 12"). Omissions and additional-but-correct facts are **not** content errors; differently-worded but compatible statements are **not** content errors.
- **Transcript span / segment**: the unit the triage step labels — a contiguous run of transcribed speech (e.g., an utterance or voice-activity chunk) that carries its own timing. Triage assigns each span one class.
- **Triage classes**: **real speech** (default); **likely pronunciation mishearing** = a low-confidence transcription of a real utterance that is phonetically close to a plausible intended word (e.g., "must" → "mouse"); **ASR hallucination** = transcribed text occurring where the recording has no corresponding voice activity, or matching the known phantom-phrase list (e.g., "I'll see you later" during silence). **Garbage attempt** = an attempt whose usable (real-speech) content is below a minimum (default: fewer than 3 usable words).
- **Probe-worthy material**: a session has probe-worthy material when the combined usable (real-speech) transcript across the three attempts is at least a small minimum (default: ≥ 30 words). Follow-ups are derived **only** from the three timed-attempt transcripts — never from earlier follow-up answers — and a follow-up answer never spawns a further follow-up.
- **Top recurring error**: the grammar-pattern label with the highest total occurrence count across the learner's recent sessions (default window: last 5 sessions), requiring at least 2 total occurrences to qualify.
- **Warm-up drill item**: one short target sentence the learner is asked to produce that exercises the corrected form of the top recurring error (a warm-up has **3** such items by default). **Pass** = the learner's transcribed response contains the corrected form and not the error form; **fail** = it does not; **incomplete** = empty/garbage/silent response (not counted as a fail).
- **Due-queue priority order**: most-overdue first; ties broken by lower recent answer-quality grade; then by oldest last-practiced date. New (no-history) questions are due but ranked **after** overdue below-mastery questions so a first run does not bury review items.
- **Trend window**: the most recent N sessions (default N = 3) in chronological order; a session where a pattern did not occur renders as 0; a pattern seen in only one session renders a single value with no arrow.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interactive interviewer / spoken follow-ups (Priority: P1)

After the learner finishes their final timed attempt on a question, the system asks 1–2 unscripted follow-up questions **out loud** — each one chosen from what the learner *actually said*: probing a gap they left, an edge case they ignored, or a "why" behind a claim they made. The learner answers each follow-up by voice within a short time budget (default 60 seconds). The follow-up answer is transcribed and run through the same per-attempt analysis, and appears in the session report in its own section.

**Why this priority**: Answering unexpected questions on the spot is the single core interview skill the current tool does not train at all — practice today is a rehearsed monologue. This slice converts the tool from a teleprompter into an interviewer and delivers value even with nothing else in this feature built.

**Independent Test**: On today's system (no other slice present), run a normal session to its last attempt; verify the system speaks at least one follow-up that references a content word the learner actually used (or names a gap in their answer), is not a reused bank question, records a voice answer under the time budget, and adds a "Follow-ups" section to the report containing the question, the transcribed answer, and that answer's grammar/fluency feedback. (Triage and pronunciation flags refine the follow-up answer only once P4 is present.)

**Acceptance Scenarios**:

1. **Given** a learner has completed all three timed attempts on a question, **When** the session reaches the follow-up stage, **Then** the system speaks 1–2 follow-up questions, each referencing a specific thing the learner said or omitted, and none drawn from any pre-written list.
2. **Given** a follow-up has been asked, **When** the learner speaks an answer within the time budget, **Then** that answer is transcribed and the report's Follow-ups section shows the question, the answer transcript, and grammar/fluency feedback for it (coverage is not scored for follow-ups — they have no key points).
3. **Given** a follow-up has been asked, **When** the learner stays silent until the time budget expires, **Then** the follow-up is recorded as unanswered (timed out), the loop continues, and the report shows the follow-up with a "no answer — timed out" note rather than failing.
4. **Given** the learner's attempts lacked probe-worthy material (below the usable-word minimum), **When** the follow-up stage runs, **Then** the system asks zero follow-ups and the report notes that no probe-worthy material was available — it never invents a generic scripted question to fill the slot.
5. **Given** a follow-up has been asked, **When** the learner requests a repeat, **Then** the system replays the spoken follow-up once without consuming the answer budget; **When** the learner skips it instead, **Then** it is recorded as unanswered and the loop continues.

---

### User Story 2 - Cross-session memory, scheduling, and warm-up (Priority: P2)

The tool remembers across sessions. (a) It surfaces each grammar pattern's occurrences over time, so every report shows that pattern's recent trend (e.g., "verb tense: 10 → 4 → 1 over the last 3 sessions"), and a stats view shows the same across all questions. (b) Every question carries a spaced-repetition schedule: questions the learner answered poorly resurface within 1–2 days, well-answered ones return at growing intervals, and a "what should I practice today" command returns the due queue. (c) Each session opens with a 30–60 second oral warm-up drill generated from the learner's top recurring error, with immediate pass/fail feedback per drill item.

**Why this priority**: Without retention mechanics, every correction the tool produces evaporates at the end of the session and never becomes a habit. Trends make progress visible, scheduling forces the right re-practice at the right time, and the warm-up converts the learner's worst recurring error into a 30-second daily rep.

**Independent Test**: With two or more past reports on record, open a new session and verify (a) the report shows a numeric per-pattern trend across the recent window and the stats view lists the same; (b) the due-queue command returns questions in priority order, with poorly-answered ones dated within 1–2 days; (c) the session begins with a spoken warm-up targeting the top recurring error and reports pass/fail per item. With no P3 present, the answer-quality grade powering scheduling falls back to grammar + fluency.

**Acceptance Scenarios**:

1. **Given** a grammar pattern (e.g., "verb tense") has occurred across the recent window, **When** a new report is written, **Then** it shows that pattern's occurrence-count trend over the recent sessions as an ordered series, including patterns that were frequent recently but absent this session (rendered as a trailing 0).
2. **Given** the learner asks "what should I practice today," **When** the due queue is computed, **Then** it returns the questions whose next-due date has arrived in the defined priority order, and is non-empty as long as any question is still below mastery.
3. **Given** a question was graded poor in its last session, **When** its schedule is updated, **Then** its next-due date is set within 1–2 days; **Given** a question was graded good/strong, **Then** its next-due interval is strictly greater than its previous interval (successively growing on repeated success).
4. **Given** the due queue contains more questions than the daily capacity (default 5), **When** the queue is presented, **Then** the highest-priority subset up to capacity is offered and the remainder is carried forward to a later day — no question is dropped.
5. **Given** the learner has a qualifying top recurring error, **When** a session starts, **Then** a 30–60 second warm-up drill targeting it is spoken, the learner responds per item, and each item gets immediate pass/fail feedback after that response (not only a summary at the end).
6. **Given** a learner with no prior history (or no qualifying recurring error), **When** a session starts, **Then** the warm-up is skipped or uses a neutral generic drill, and nothing in the trends or schedule presentation implies data that does not exist.

---

### User Story 3 - Content coverage scoring (Priority: P3)

For each question, the system derives 5–7 key points from the ideal answer once and stores them (keyed to the question, in the learner's local data — never written back into the question bank). After each attempt it marks every key point as **covered**, **partial**, or **missed**, shows how coverage changed across the three rounds, and flags content errors (factual contradictions against the ideal answer) clearly separate from grammar errors. The final round's stated goal becomes "all key points within the time budget."

**Why this priority**: Interviews grade content as much as delivery, and the current tool is blind to content — under the 4 → 3 → 2 time squeeze the learner silently drops key points and the report never notices. Coverage scoring makes that loss visible and turns the final round into a content-completeness target.

**Independent Test**: Run a question whose ideal answer has known key points; deliberately omit one and state one fact wrong; verify the report lists each key point as covered/partial/missed per round, shows the across-round delta, and lists the wrong fact as a content error in a section separate from grammar errors.

**Acceptance Scenarios**:

1. **Given** a question with an ideal answer, **When** key points are first needed, **Then** 5–7 key points are derived and stored in local state keyed by question id + ideal-answer content version, so they are not re-derived every session.
2. **Given** a completed attempt, **When** coverage is scored, **Then** every key point is marked covered, partial, or missed, and the report shows these per attempt with the round-over-round aggregate delta.
3. **Given** the learner states a fact mutually exclusive with the ideal answer, **When** the report is produced, **Then** that contradiction is listed as a content error in its own section, distinct from grammar errors, naming both the learner's claim and the ideal answer's claim; an omission or an additional correct fact is not flagged as a content error.
4. **Given** the third (final) round, **When** its goal is stated to the learner, **Then** the goal is "all key points within the time budget," and the report reflects final-round coverage against that goal.
5. **Given** a question whose ideal answer is later edited, **When** the next session runs, **Then** the system detects the change (via a content version), re-derives the key points, bumps the version, and never presents a misleading coverage delta that mixes the old and new key-point versions.

---

### User Story 4 - Trustworthy feedback pipeline (Priority: P4)

Before any grammar analysis, transcript spans are triaged into three classes: **real speech**, **likely pronunciation mishearing** (e.g., "must" → "mouse"), and **ASR hallucination** (e.g., "I'll see you later" during silence). Hallucinations are excluded from all analysis and metrics. Likely mishearings are reported in a separate "Pronunciation flags" section instead of being misclassified as grammar errors. And every generated learning artifact (improved answer, flashcards, drill sentences) is checked for factual consistency against the ideal answer before the report is written; contradictions are corrected or dropped.

**Why this priority**: Wrong feedback is worse than no feedback. The current pipeline has classified a pronunciation artifact as a "missing verb" grammar error and produced an improved answer that named the wrong exception — both actively mislead a learner who trusts the tool. This slice is a correctness guarantee that protects every other slice's output.

**Independent Test**: Feed a transcript containing (i) a known silence-hallucination phrase and (ii) a known mishearing; verify the hallucination appears nowhere in grammar evidence, metrics, or coverage, and the mishearing appears only in the Pronunciation flags section. Separately, force a generated artifact to contain a fact contradicting the ideal answer and verify it is corrected or dropped before the report is written.

**Acceptance Scenarios**:

1. **Given** a transcript span that is an ASR hallucination, **When** the pipeline runs, **Then** that span appears in no grammar evidence, no fluency metric, and no coverage judgment (metrics are computed over real-speech spans only).
2. **Given** a span that is a likely pronunciation mishearing, **When** the report is produced, **Then** it appears in a "Pronunciation flags" section and is never counted as a grammar error.
3. **Given** a generated learning artifact that contains a fact mutually exclusive with the ideal answer, **When** the consistency check runs before writing, **Then** the contradiction is corrected or the artifact is dropped — it never reaches the written report.
4. **Given** an entire attempt that triages to empty or garbage, **When** the pipeline runs, **Then** no grammar patterns or coverage judgments are fabricated from it, the recording is preserved, and the report notes the empty/unusable attempt.

---

### User Story 5 - Question-type expansion (Priority: P5)

Alongside today's definition-style questions, the bank supports two new question types: **behavioral / STAR** ("Tell me about a time you…") and **hypothetical scenario** ("If your app ANRs on startup, how would you…"). Each type gets type-specific guidance in the report — a STAR-structure check for behavioral answers and conditional-form guidance for hypotheticals. All types keep the existing three-attempt 4 / 3 / 2 structure.

**Why this priority**: Behavioral and hypothetical questions are standard real interview formats the tool can't represent today. Behavioral questions force past-tense narration — the learner's most frequent error class — and hypotheticals exercise conditionals, so both directly target known weaknesses while broadening realism. It ranks last only because it widens coverage rather than fixing a correctness or retention gap.

**Independent Test**: Add one behavioral and one hypothetical question to the bank; run each; verify the report applies type-appropriate guidance (which of S/T/A/R were present for the behavioral answer; conditional-form focus citing the learner's own clauses for the hypothetical) and that existing definition questions are unaffected.

**Acceptance Scenarios**:

1. **Given** a question declared as behavioral/STAR, **When** the report is produced, **Then** it includes a STAR-structure check identifying which of Situation / Task / Action / Result were present in the answer.
2. **Given** a question declared as hypothetical, **When** the report is produced, **Then** it includes a labeled conditional/future-form guidance section that cites at least one of the learner's own clauses and flags where a conditional was expected but not used.
3. **Given** existing questions with no declared type, **When** they run, **Then** they are treated as definition-style and behave exactly as before this feature.

---

### Edge Cases

- **Silent follow-up**: learner says nothing → time out, record the follow-up as unanswered, continue the loop, surface it in the report.
- **Follow-up repeat / skip**: the learner may replay a follow-up once (the answer budget is not consumed) or skip it; a skip is recorded as unanswered, like a timeout.
- **Recording-hardware failure during a follow-up or warm-up** (as distinct from silence): the stage is skipped with a recorded reason and the loop continues; the existing abort/interrupt handling applies to these new stages too.
- **Empty/garbage attempt**: triage classifies the whole attempt as garbage → no grammar/coverage is fabricated; the recording is preserved; the report flags the unusable attempt.
- **No probe-worthy material**: usable transcript below the minimum → ask zero follow-ups and say why; never substitute a scripted question.
- **Question with no prior history**: treated as due but ranked after overdue below-mastery questions; the report shows a first-session baseline rather than a fake trend; warm-up is generic or skipped.
- **Due queue larger than daily capacity**: present the highest-priority capacity-sized subset and carry the rest forward; never silently drop a due question.
- **Due queue empty (all questions mastered)**: the daily-loop command tells the learner nothing is due and offers on-demand practice rather than erroring; the queue is empty *only* when nothing is below mastery.
- **Analysis unavailable mid-session**: save the raw audio and transcripts, mark the session analysis-pending, write whatever deterministic parts are possible, and never lose a recording. Because grammar, triage, and coverage are all analysis-dependent, none of them are written when analysis is unavailable — so no untriaged grammar evidence can leak into a degraded report. A pending session is resumable later (see FR-035a).
- **Warm-up generation fails / analysis unavailable at warm-up time**: skip the warm-up and proceed directly to attempt 1.
- **Ideal answer edited after key points were derived**: detect via the content version, re-derive and version the key points, and score only against the current version; do not present cross-version coverage deltas as if comparable.
- **Single-data-point trend**: a pattern seen in only one session shows a single value, not a misleading arrow.
- **Pattern that disappeared**: a previously frequent pattern absent this session still shows its declining trend (trailing 0) so the learner sees the win.
- **Contradiction-heavy answer**: when most key points are missed or wrong, still produce a coverage report and list content errors rather than aborting.
- **Behavioral/hypothetical coverage**: key-point derivation and coverage adapt to the type (the four STAR components are the key points for a behavioral question).

## Requirements *(mandatory)*

### Functional Requirements

**Interactive interviewer (P1)**

- **FR-001**: After the learner's final timed attempt, the system MUST generate 1–2 follow-up questions derived **solely** from the learner's three timed-attempt transcripts — referencing a gap, an edge case, or a "why" in what they said — and MUST NOT draw follow-ups from the question bank or any pre-written list. Follow-up answers are never themselves a source for further follow-ups.
- **FR-002**: The system MUST ask each follow-up aloud and MUST record the learner's spoken answer within a configurable time budget (default 60 seconds). The budget starts when the spoken prompt finishes playing and ends at the budget or at detected end-of-speech, whichever comes first.
- **FR-002a**: During a follow-up the learner MUST be able to (a) replay the spoken follow-up **once** on demand without consuming the answer budget, and (b) **skip** the follow-up; a skipped or fully-silent follow-up is recorded as unanswered.
- **FR-003**: On follow-up timeout (no speech within the budget), the system MUST record the follow-up as unanswered, continue the session, and represent it in the report — it MUST NOT crash or block report generation.
- **FR-004**: Each follow-up answer MUST pass through the same **per-attempt** analysis that the timed attempts receive in the current system — transcription, grammar feedback, and fluency metrics — and, when P4 is present, triage and pronunciation flags. Coverage scoring MUST NOT be applied to follow-ups, which have no key points.
- **FR-005**: The report MUST contain a dedicated follow-ups section listing, per follow-up, the question asked, the answer transcript (or a timed-out note), and its feedback.
- **FR-006**: When no probe-worthy material exists (usable transcript below the minimum), the system MUST ask zero follow-ups and record why, rather than substituting a generic scripted question.
- **FR-007a**: The learner MUST be able to disable follow-ups and/or the warm-up for a run, restoring the legacy single-question flow; both are enabled by default.

**Cross-session memory, scheduling, warm-up (P2)**

- **FR-007**: The system MUST present each grammar pattern's occurrences across sessions, computed from the existing saved session reports (no new separate occurrence store is required); the same report-derived data backs both the in-report trend and the stats view.
- **FR-008**: Each session report MUST show, for each pattern found this session **or** seen in the recent trend window, that pattern's occurrence trend as an ordered numeric series in chronological order (e.g., "10 → 4 → 1"), zero-filling sessions where the pattern did not occur.
- **FR-009**: The system MUST provide a stats view that displays per-pattern occurrence trends across sessions for all questions. This extends the existing cross-session dashboard rather than introducing a second command that does the same thing.
- **FR-010**: Every question MUST carry a spaced-repetition schedule (an interval state and a next-due date) updated after each session from the Answer-Quality Grade. When content coverage (P3) is not available, the grade MUST fall back to grammar severity + fluency so scheduling still functions without P3.
- **FR-011**: A question's next-due date MUST be set from the spaced-repetition interval ladder (Key Definitions): a **poor** grade resurfaces it in 1 day (interval reset to base) and a **fair** grade in 2 days, while **good** / **strong** grades set an interval strictly greater than the previous one (× 2 / × 2.5, capped at 21 days until mastery), so consecutive successes produce successively growing intervals.
- **FR-012**: The system MUST provide a "what to practice today" command that returns the due queue — questions whose next-due date has arrived — in the defined due-queue priority order.
- **FR-013**: The due queue MUST be non-empty whenever any question remains below mastery (as defined in Key Definitions).
- **FR-013a**: Mastered questions MUST be excluded from the active due queue (so the queue is empty only when every question is mastered) but MUST return for a single maintenance review at the interval ceiling (default 30 days); a maintenance review graded below **strong** demotes the question back into normal rotation.
- **FR-014**: A question with no prior history MUST be treated as due, ranked after overdue below-mastery questions so a first run does not bury review items.
- **FR-015**: When the due queue exceeds the daily capacity (default 5, learner-configurable), the system MUST present the highest-priority subset up to capacity and carry the remainder forward; no due question is dropped.
- **FR-016**: Each session MUST open with a 30–60 second oral warm-up drill of **three items** generated from the learner's top recurring error, giving **immediate** pass/fail feedback after each drill item per the warm-up pass/fail rule. An empty/garbage/silent drill response is marked incomplete, not failed, and the loop proceeds. If warm-up generation cannot run, the warm-up is skipped and the loop proceeds to attempt 1.
- **FR-017**: For a learner with no qualifying recurring-error history, the warm-up MUST be skipped or use a neutral generic drill, and no trend/schedule presentation may imply history that does not exist.
- **FR-017a**: When the due queue is empty because all questions are mastered, the daily-loop command MUST inform the learner that nothing is due and offer on-demand practice rather than erroring.

**Content coverage (P3)**

- **FR-018**: For each question, the system MUST derive its key points once and persist them in the learner's local state, keyed by question id + ideal-answer content version — **never** written into any shipped or user question-bank file. The count is 5–7 for definition and hypothetical questions; behavioral questions use the four STAR components as their key points.
- **FR-019**: After each attempt, the system MUST mark every key point as covered, partial, or missed per the Coverage-state definitions.
- **FR-020**: The report MUST show coverage per attempt and the coverage delta across the three rounds — per key point (state per round) and in aggregate (the aggregate-coverage metric, final minus first round).
- **FR-021**: The system MUST flag content errors (mutually-exclusive contradictions against the ideal answer) in a section separate from grammar errors, naming both the learner's claim and the ideal answer's claim; omissions and additional correct facts MUST NOT be flagged as content errors.
- **FR-022**: The final round's stated goal MUST be "all key points within the time budget" (for behavioral questions, "all STAR components within the time budget"), and the report MUST reflect final-round coverage against that goal.
- **FR-023**: If a question's ideal answer changes (detected via a content version derived from its normalized text), the system MUST re-derive the key points and bump the version, and MUST NOT present coverage comparisons that mix key-point versions as if comparable.

**Trustworthy feedback pipeline (P4)**

- **FR-024**: Before grammar analysis, the system MUST triage every transcript span into one of: real speech, likely pronunciation mishearing, or ASR hallucination, per the Triage-class definitions.
- **FR-025**: Spans classified as ASR hallucination MUST be excluded from all analysis and metrics — grammar evidence, fluency metrics, and coverage alike; fluency metrics MUST be computed over real-speech spans only.
- **FR-026**: Spans classified as likely pronunciation mishearings MUST be reported in a separate "Pronunciation flags" section and MUST NOT be counted as grammar errors.
- **FR-027**: Every generated learning artifact MUST be checked for factual consistency against the ideal answer before the report is written; any mutually-exclusive contradiction MUST be corrected or the artifact dropped. This applies to whichever artifacts a run actually produces (see Assumptions — Artifact scope: drill/warm-up sentences in any mode; the improved-answer rewrite and flashcards in the modes that produce them).
- **FR-028**: No ASR-hallucination text may ever appear in grammar evidence in any written report.
- **FR-029**: When an entire attempt triages to empty or garbage, the system MUST NOT fabricate grammar or coverage findings from it, MUST preserve the recording, and MUST note the unusable attempt in the report.

**Question types (P5)**

- **FR-030**: The question bank MUST support three question types — definition (existing), behavioral/STAR, and hypothetical scenario — via an additive optional `type` field; questions that omit it default to definition. Adding this field MUST NOT bump the question-file schema version, and existing question files MUST load unchanged (the loader accepts `type` rather than warning on it). All types keep the existing three-attempt 4 / 3 / 2 structure.
- **FR-031**: For behavioral/STAR questions, the report MUST include a STAR-structure check identifying which of Situation / Task / Action / Result were present in the answer.
- **FR-032**: For hypothetical questions, the report MUST include a labeled conditional/future-form guidance section that cites at least one of the learner's own clauses and flags constructions where a conditional was expected.
- **FR-033**: Key-point derivation and coverage scoring MUST adapt to the question type (the STAR components serve as the key points for a behavioral question).

**Cross-cutting / loop integration**

- **FR-034**: The system MUST support running the full daily loop — due-question selection → warm-up → question + three attempts → 1–2 follow-ups → report — end to end in a single command flow, with each stage advancing automatically.
- **FR-035**: When automated analysis is unavailable at any point in a session (a model/load failure, or in cloud mode a failed preflight/request), the system MUST save the raw audio and transcripts, mark the session analysis-pending, produce whatever deterministic report parts are possible, and never lose a recording. No grammar/coverage/triage output is written for the unavailable portion.
- **FR-035a**: A session left analysis-pending MUST be resumable — the learner can re-run analysis over the preserved audio/transcripts when analysis is available. Until resolved, the underlying question MUST be treated as un-graded (kept due, not counted as well-answered).
- **FR-036**: All new report content MUST be additive and optional: any new structured key in the report's metadata is optional and absent-by-default (mirroring the existing optional keys), narrative sections (follow-ups, coverage, content errors, pronunciation flags, type guidance, trend lines) live in the report body, and reports lacking the new data MUST continue to render and parse with the report schema version unchanged. Follow-ups are stored as additive optional structured data so a report round-trips; follow-up grammar findings are aggregated into cross-session trends, marked as originating from a follow-up.
- **FR-037**: All user-facing output MUST remain English-only and CLI-only; no GUI, web interface, or multi-user support is introduced.
- **FR-038**: The system MUST remain offline-first: no new mandatory network dependency. The new analysis steps MUST follow the existing routing — on-device by default, the existing opt-in cloud mode when the learner selects it — and the same privacy disclosure applies to any data the cloud mode sends.
- **FR-039**: All new spoken output (follow-up prompts, warm-up prompts) MUST route through the existing speech-synthesis path and all new recording/transcription through the existing recognition path — no new engine integration sites — and tests for the new steps MUST use cached/recorded fixtures rather than live model calls.
- **FR-040**: Any new persistent learner state that is meant to be inspectable or editable by the learner (e.g., the per-question schedule and mastery state) MUST be stored as YAML in the user config/data area, consistent with the project's user-config conventions; purely internal caches need not be YAML but MUST NOT be presented to the learner as configuration.

### Key Entities *(include if feature involves data)*

- **Question (extended)**: the existing question (id, prompt text, ideal answer, tags, difficulty), now additionally carrying an optional **type** (definition / behavioral / hypothetical). Its derived key points and review schedule are associated by question id in local state, not embedded in the question file.
- **Key Point**: one atomic fact derived from a question's ideal answer (5–7 for definition/hypothetical; the four STAR components for behavioral), plus a derivation **version** tied to the ideal answer's content so edits trigger re-derivation.
- **Coverage Record**: per attempt, the covered/partial/missed status of each key point, the round-over-round delta, and the key-point version it was scored against.
- **Content Error**: a mutually-exclusive contradiction between the learner's words and the ideal answer (learner's claim + ideal answer's claim), tracked separately from grammar errors.
- **Follow-up**: a system-generated, unscripted question grounded in the learner's attempt transcripts (with the gap/word it probes), the learner's transcribed answer (or timed-out marker), and the feedback for that answer.
- **Warm-up Drill**: three drill items targeting the top recurring error, each with a target sentence and a pass / fail / incomplete result.
- **Pattern Trend / Cross-session Memory**: per grammar-pattern label, the ordered series of occurrence counts across the recent window, derived from saved reports and used in reports and the stats view.
- **Review Schedule / Mastery State**: per question, the latest answer-quality grade, the current interval, the next-due date, and whether the question has reached mastery.
- **Answer-Quality Grade**: the per-session poor/fair/good/strong band that drives scheduling, with the defined coverage-primary signal and grammar+fluency fallback.
- **Transcript Span Triage**: per span, its classification as real speech, likely mishearing, or hallucination — the gate that protects all downstream analysis.
- **Session Report (extended)**: the existing report, now additionally carrying the follow-ups section, coverage section, content-errors section, pronunciation-flags section, per-pattern trend lines, and type-specific guidance — all additive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a usability check of the daily loop, 100% of stages (due selection → warm-up → question + three attempts → follow-ups → report) advance automatically with no input required between stages other than the learner's own spoken attempts and answers, ending in a written report.
- **SC-002**: In a sample of reports where the underlying data exists, 100% include the per-pattern occurrence trend versus previous sessions, the per-attempt coverage status with across-round delta, and a follow-ups section; reports where that data legitimately does not exist omit the section without error.
- **SC-003**: Across a labeled validation set, 0% of phantom transcription artifacts (text produced where the learner did not speak) appear anywhere in the report's grammar feedback.
- **SC-004**: Against a labeled set seeded with known contradictions, 100% of learning aids included in written reports match the reference answer's facts — every seeded contradiction is corrected or removed before it reaches the report, judged by a reviewer against the reference answer.
- **SC-005**: (a) Whenever at least one question is below the mastery threshold, the due queue is non-empty. (b) A question graded poor in a session reappears in the due queue within 1–2 days. Both are verifiable from the schedule state and queue output.
- **SC-006**: Across a labeled validation set, items the learner pronounced unclearly (and were mis-transcribed) are surfaced only as pronunciation feedback and are miscounted as grammar mistakes 0% of the time.
- **SC-007**: No recording is ever lost: in 100% of sessions where automated analysis cannot run, the learner's raw audio and transcripts are preserved and recoverable, and the report indicates analysis is incomplete and can be retried.
- **SC-008**: On a labeled set of behavioral and hypothetical answers, the report's type-specific guidance is present and correct in 100% of cases — for behavioral answers it correctly identifies which narrative components (situation/task/action/result) were present, and for hypotheticals it focuses feedback on conditional/future phrasing — verified against human labels.
- **SC-009**: In 100% of multi-round sessions, the report shows each key point's first-round and final-round coverage side by side, so a reviewer can identify from the report alone every key point that was covered early but dropped under time pressure.
- **SC-010**: In 100% of cases where a follow-up is asked, a reviewer can point to the specific word or omission in the learner's own answer that the follow-up probes, and the follow-up is not a reused pre-written practice question.
- **SC-011**: In 100% of warm-up runs, an explicit pass/fail (or incomplete) result is reported for each drill item immediately after the learner's response, and the warm-up is designed to take roughly 30–60 seconds.
- **SC-012**: Reports created before this feature, and sessions that lack the new data, continue to open and display correctly with no errors and no loss of their original content.

## Out of Scope

- Shadowing mode (repeat-after-the-model practice).
- Cold-first attempt ordering (attempting before hearing the ideal answer).
- Minimal-pair pronunciation drills.
- Listening-comprehension exercises.
- Any GUI or web interface.
- Multi-user support / per-user accounts.
- Question types beyond definition, behavioral/STAR, and hypothetical; and numeric/letter grading of STAR or conditional quality (the type checks are presence/structure/emphasis checks, not graded rubrics).
- Changing the report schema version or making any new report field mandatory.
- Introducing a new always-on network dependency (the existing cloud mode stays opt-in).

## Assumptions

- **State storage**: derived key points (with their version), per-question review schedules and mastery state, and any per-session derived data live in the learner's local data area and are never written back into the shipped or user question-bank file; cross-session pattern trends are computed from the existing saved session reports. Learner-inspectable/editable state is stored as YAML per project conventions (FR-040).
- **Key-point versioning**: key points are keyed to a content version derived from the ideal answer's normalized text (trimmed, internal whitespace collapsed); a meaningful edit changes that version and triggers re-derivation, while whitespace-only edits do not.
- **Engine routing**: the new analysis steps (follow-up generation, key-point derivation, coverage scoring, content-error detection, span triage, artifact consistency check, warm-up generation) use the same routing as today — the on-device model by default, the opt-in cloud model when selected — reusing the existing engine paths (FR-039), and degrade per FR-035 when no analysis is available.
- **Artifact scope across modes**: drill/warm-up sentences are generated in any mode that runs analysis. The improved-answer rewrite and the paste-ready flashcards remain produced by the existing opt-in cloud coaching step (this feature does not port them to the default on-device flow); FR-027's consistency guarantee applies to whichever artifacts a given run actually produces. Coverage scoring and content-error flagging run wherever analysis is available (on-device or cloud).
- **Grade & mastery tuning**: the Answer-Quality Grade bands, the interval ladder, and the mastery rule in Key Definitions are the confirmed defaults (poor → 1 day, fair → 2 days, good → × 2, strong → × 2.5, cap 21 days, maintenance ceiling 30 days, mastery = two consecutive **strong** with zero content errors). The exact coverage-percentage boundaries (0.50 / 0.75 / 0.95) remain tunable during planning without changing this observable contract.
- **Daily capacity**: defaults to 5 and is learner-configurable; overflow carries forward.
- **Follow-up count**: the system asks 2 follow-ups when there are at least two distinct probe candidates, otherwise 1, otherwise 0; follow-ups and the warm-up can be disabled (FR-007a) for the legacy single-question flow.
- **Preserved foundations**: the existing 4 / 3 / 2 timed-attempt structure, fluency metrics, grammar pipeline, ideal-answer reference display, existing cross-session dashboard, and report file format are preserved and extended, not replaced.
- **Daily loop surface**: the loop is surfaced through the practice flow with due-question selection; practicing a specific question on demand is preserved.
- **Validation sets**: success criteria that cite "a labeled validation set" assume a small curated set, authored from real prior sessions independently of the triage/coverage implementation (so the checks are external, not self-graded), with a stated minimum size and a labeling rubric defined during implementation.

## Dependencies

- Reuses the existing on-device engines via their existing integration paths: speech synthesis (to speak follow-ups and warm-up prompts), speech recognition (to transcribe follow-up answers and drill responses), and the analysis model (local or opt-in cloud) for all generative/analytic steps.
- Builds on the existing per-session report format and the existing cross-session dashboard.
- The improved-answer rewrite and flashcards consumed by FR-027 are the artifacts produced by the existing opt-in cloud coaching step.
- Inherits the project's constitutional constraints: offline-first after model download, English-only, CLI-only, user config in YAML, swappable engines behind single integration points, additive report schema (version unchanged), and no recording ever lost.
