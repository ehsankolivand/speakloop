# Feature Specification: Post-Session Interactive Debrief

**Feature Branch**: `002-post-session-debrief`

**Created**: 2026-05-20

**Status**: Draft

**Input**: User description: "Improve the post-session feedback experience to make the LLM-generated grammar guidance actually educational and to keep the practice loop closed inside the terminal — with a UX that the user actually wants to return to every morning."

## Overview

A daily user practices spoken-English interview answers through a 4/3/2 attempt cycle and, at session end, receives a written report. Today that report is (1) too noisy to act on — wrong grammar labels, evidence that is speech-recognition garble, and generic fixes — and (2) delivered by dumping a file path to the shell, forcing the user to leave the tool, open the file elsewhere, read it, and relaunch to try again. This feature raises the quality bar on the feedback content (accurate Persian-L1 error labels, verbatim-anchored corrections, impact ranking, a single "top priority") and replaces the file-path dump with an in-terminal debrief that renders the report visually, reads the educational parts aloud in the correct pronunciation, and offers a one-keypress replay — closing the practice loop where the user is most motivated to act: immediately after speaking.

## Clarifications

### Session 2026-05-20

- Q: When evidence can't be classified as ASR garble vs. a genuine error, drop or keep it? → A: Drop when unsure — favor precision (no garble surfaced, even at the cost of missing some real errors).
- Q: Can the single "Top priority" be a fluency issue when grammar patterns also exist? → A: Yes — the most-impactful issue wins by a defined rule, whether grammar or fluency.
- Q: How does the user expand collapsed transcripts during the debrief? → A: A dedicated key at the menu (e.g., `t`) toggles full transcripts in-place, alongside r/n/q.
- Q: Where does the "Because:" explanation come from for open-bucket (non-catalog) patterns? → A: LLM-provided, verified non-empty and coherent — same accuracy bar as catalog patterns.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy, actionable feedback content (Priority: P1)

As a Persian-L1 speaker preparing for engineering interviews, when I finish a session I want feedback that names my actual mistakes correctly, points to the exact words I said, shows me the corrected version, and tells me the one thing to fix first — so I can act on it instead of second-guessing whether the tool is even right.

**Why this priority**: This is the root cause of the user's distrust. Even a beautiful debrief is worthless if it reads wrong labels and garbled evidence aloud. Accurate, specific feedback is the precondition for every other part of the loop.

**Independent Test**: Run a session (or replay a fixed transcript set through the analyzer) containing known Persian-L1 errors. Verify each reported pattern has a catalog-accurate label, that every piece of evidence is a verbatim quote forming coherent words, that each fix names the user's words and a concrete correction, and that one "top priority" is surfaced. Delivers value as an improved report file even before any UI changes.

**Acceptance Scenarios**:

1. **Given** a transcript containing "I like to programming", **When** the analyzer runs, **Then** the pattern is labelled as gerund/infinitive confusion (not "auxiliary be/do drop") and the fix reads "You said: 'I like to programming'. Better: 'I like programming' (or 'I like to program'). Because: <one-line reason>."
2. **Given** a transcript containing "eight year experience", **When** the analyzer runs, **Then** a plural/preposition pattern is reported anchored on those verbatim words with a corrected version ("eight years of experience").
3. **Given** a transcript containing "I like my job even bigger than ten years ago", **When** the analyzer runs, **Then** a comparative-form pattern is reported and the correction uses "more" rather than "bigger".
4. **Given** an evidence candidate that is speech-recognition garble (e.g. "Killing RT check") whose words do not form coherent grammar, **When** the analyzer evaluates it, **Then** that evidence — and any pattern that depends solely on it — is dropped from the report.
5. **Given** three attempts where filler density fell and speech rate rose, **When** the report is built, **Then** a cross-attempt narrative states what improved, what stayed the same, and a single "Top priority for next session".
6. **Given** multiple detected patterns, **When** they are presented, **Then** they are ordered by impact on interview comprehensibility rather than by raw frequency.

---

### User Story 2 - In-terminal visual debrief with one-keypress replay (Priority: P1)

As a daily user, when the session ends I want the report rendered right there in the terminal — formatted, with the top priority prominent and each correction laid out as a card — and a menu that lets me replay the same question, pick a new one, or quit, so I never have to leave the tool to read my feedback or to try again.

**Why this priority**: This closes the loop. Without it the user disengages at the exact moment feedback matters most. It is independently valuable on Phase-B content (metrics + transcripts + narrative) even if grammar analysis is unavailable.

**Independent Test**: Finish a session and confirm the report renders in-place (not raw markdown, no file-path dump as the only output), the top-priority callout is visually prominent, grammar patterns appear as three-line cards, transcripts are collapsed by default, and a menu accepting r/n/q (and replay/new/quit) appears. Choosing replay returns to the listen phase for the same question; new opens the question picker; quit returns to the shell.

**Acceptance Scenarios**:

1. **Given** a completed session, **When** the report is written, **Then** the terminal renders the report contents formatted in-place with visual hierarchy (headers, tables, and structure rendered, not raw markdown).
2. **Given** a report with a top priority, **When** it renders, **Then** the "Top priority for next session" appears in a bordered box/banner above the grammar patterns list, visually distinct from ordinary headers.
3. **Given** a grammar pattern, **When** it renders, **Then** it appears as a card with three visually distinct lines in fixed order: "You said: …", "Better: …", "Because: …".
4. **Given** an attempt summary, **When** it renders, **Then** WPM and filler-density trends are colour-coded green (improved), yellow (flat), or red (worsened) across attempts.
5. **Given** a transcript of 153 words, **When** the debrief renders, **Then** the transcript shows collapsed as a single line with the first ~10 words and an indicator like "+143 words", and the user can expand it explicitly to see the full text.
6. **Given** the menu is shown, **When** the user presses `r` or types `replay`, **Then** the same question replays; **When** the user presses Enter on the default selection, **Then** replay is chosen (default is replay, with arrow-key navigation).
7. **Given** the user chooses replay, **When** the next cycle starts, **Then** the screen clears and goes straight to "press space to begin attempt 1" with no model reload, no progress bars, no "Loading models…", and no doctor pre-check — within 3 seconds.

---

### User Story 3 - Read-aloud corrections synced to the screen (Priority: P2)

As a learner who wants to hear what I should have said, when the debrief opens I want the tool to read the educational parts aloud — the cross-attempt narrative, the top priority, and each correction's explanation and corrected version — while highlighting the section being read, so I hear the correct pronunciation and can follow along; and I want to skip the audio with any key.

**Why this priority**: Hearing the corrected version is a distinct learning channel the user explicitly values, but the loop still closes without it (visual debrief + menu suffice). Builds on US2.

**Independent Test**: With audio enabled, confirm the announcement line appears, only the educational parts are read aloud (no transcripts, no raw metrics tables), the currently-read section is highlighted, a progress indicator ("3 of 6 sections") is shown, sections play in the order narrative → top priority → patterns (ranked), and any keypress skips the rest and jumps to the menu. With `--no-audio`, confirm audio is skipped entirely and the menu is reachable immediately.

**Acceptance Scenarios**:

1. **Given** audio is enabled, **When** the debrief opens, **Then** a one-line announcement "🔊 Reading your feedback aloud — press any key to skip." appears before audio starts.
2. **Given** audio is playing, **When** a section is being read, **Then** that section is visually highlighted and a progress indicator (e.g. "3 of 6 sections") is visible.
3. **Given** audio is playing, **When** the user presses any key, **Then** the remaining audio stops immediately and the menu appears with no confirmation prompt.
4. **Given** the educational content, **When** it is read aloud, **Then** only the cross-attempt narrative, the top priority, and each pattern's explanation + corrected version are spoken — transcripts and raw metrics tables are never spoken — in the order narrative → top priority → patterns (ranked).
5. **Given** the `--no-audio` flag, **When** the session ends, **Then** no audio plays and the visual debrief plus menu appear immediately.

---

### User Story 4 - Graceful degradation and first-time guidance (Priority: P3)

As a user who may not have the grammar model installed, or whose audio output fails, I still want a working debrief and a clear path forward; and the very first time I see a debrief I want one line orienting me to what is about to happen.

**Why this priority**: Robustness and onboarding. The core loop must never hang or dead-end, but these paths are exercised less often than the happy path.

**Independent Test**: Remove/disable the grammar model and confirm the debrief still runs on Phase-B content with a single explanatory line replacing the grammar section. Force a TTS failure and confirm the visual debrief continues and the menu appears immediately. Run with no prior reports present and confirm the first-time orientation line appears; run with prior reports present and confirm it does not.

**Acceptance Scenarios**:

1. **Given** the grammar model is not installed, **When** the debrief runs, **Then** it presents Phase-B content (metrics, transcripts, cross-attempt narrative if available) and replaces the grammar patterns section with the single line "Grammar pattern analysis is available when the LLM model is installed."
2. **Given** audio output fails for any reason, **When** the debrief runs, **Then** the visual debrief continues and the menu appears immediately without hanging.
3. **Given** no previous reports exist in the session history, **When** the first debrief opens, **Then** one extra line appears above the report: "This is your feedback. I'll read the key parts aloud, then you can replay this question or pick a new one."
4. **Given** at least one previous report exists, **When** a debrief opens, **Then** the first-time orientation line is not shown.

---

### Edge Cases

- **All attempts silent / empty transcripts**: No grammar patterns are produced; the debrief still renders the (empty) metrics and transcripts and reaches the menu. The top priority degrades to the exact message "No content captured this session — focus on speaking out loud next time." rather than a fabricated correction.
- **Analyzer returns zero coherent patterns** (all candidates dropped as garble): the grammar section shows the exact line "No actionable grammar patterns detected this session." rather than empty or fabricated cards; the cross-attempt narrative and top priority still appear.
- **Mid-debrief abort (Ctrl+C)**: returns to the shell cleanly without corrupting the already-written report or leaving temp audio behind.
- **User expands a transcript then triggers replay**: expansion state is discarded on replay; the next cycle starts clean.
- **Replay chosen many times in a row**: each cycle writes a distinct report (disambiguated session id) and no model reload occurs on any replay.
- **Terminal too narrow / no colour support**: cards, boxes, and colour coding degrade to a readable plain layout rather than breaking.
- **A correction's "Better" version is identical to what the user said** (false positive slipped through): the pattern is suppressed rather than shown as a no-op card.
- **Keypress arrives during the announcement line, before the first section plays**: treated as a skip; jumps straight to the menu.

## Requirements *(mandatory)*

### Functional Requirements — Feedback content quality

- **FR-001**: The grammar analyzer MUST assign every reported pattern a label drawn from a defined Persian-L1 English error catalog (e.g. gerund/infinitive confusion, comparative-form errors, plural/singular agreement, article omission distinguishing proper vs common nouns), not a generic English-grammar catalog.
- **FR-002**: The catalog MUST ship with a seed set of Persian-L1 patterns and MUST preserve the existing open-bucket mechanism so that non-seed patterns can still be surfaced when they recur (occurrence threshold), without requiring the catalog to be exhaustive.
- **FR-003**: Each reported pattern MUST include a one-line explanation of why the error happens (the linguistic-transfer reason), written for a B1–B2 learner. For catalog patterns this explanation comes from the catalog; for open-bucket (non-catalog) patterns it is supplied by the analyzer's language model and MUST be verified non-empty and coherent before display, held to the same accuracy bar as catalog patterns.
- **FR-004**: Each suggested fix MUST reference the user's actual words verbatim and show a concrete corrected version inline, in the form "You said: 'X'. Better: 'Y'. Because: Z."
- **FR-005**: Reported patterns MUST be ordered by impact on interview comprehensibility, not by raw occurrence frequency.
- **FR-006**: The analyzer MUST drop any evidence quote whose words do not form coherent grammar (clearly speech-recognition garble), and MUST drop any pattern left without coherent verbatim evidence. When coherence is uncertain, the analyzer MUST default to dropping the quote (favor precision over recall): surfacing garble is never acceptable, even at the cost of missing some genuine errors.
- **FR-007**: Every evidence quote MUST remain a verbatim substring of the attempt transcript it cites (existing guarantee preserved).
- **FR-008**: The report MUST include a short cross-attempt narrative identifying what improved across the 4/3/2 rounds, what stayed the same, and the single most important focus for the next session, surfaced as a distinct "Top priority for next session" highlight. The Top priority MUST be the single most impactful issue by a defined rule — either a grammar pattern or a fluency dimension (e.g., severe filler density) — selected deterministically; a fluency issue MAY be chosen as Top priority even when grammar patterns also exist if it outranks them.
- **FR-009**: The analyzer MUST suppress any pattern whose corrected version is identical to the user's original words.

### Functional Requirements — Interactive debrief (visual)

- **FR-010**: On session end, the system MUST render the report contents in the terminal in-place with formatting and visual hierarchy (rendered headers, tables, and structure — not raw markdown text), instead of only printing a file path.
- **FR-011**: The "Top priority for next session" MUST be rendered with visual prominence — a bordered box or banner positioned above the grammar patterns list — distinct from ordinary section headers.
- **FR-012**: Each grammar pattern MUST render as a card with three visually distinct lines in fixed order: "You said: …", "Better: …", "Because: …".
- **FR-013**: WPM and filler-density trends in the attempt summary MUST be colour-coded: green if improved across attempts, yellow if flat, red if worsened.
- **FR-014**: Transcripts MUST be shown collapsed by default — one line per attempt showing the first ~10 words plus a remaining-word-count indicator (e.g. "+143 words") — and the user MUST be able to expand them explicitly via a dedicated key at the menu (e.g. `t`) that toggles full transcripts in-place, alongside the replay/new/quit options.
- **FR-015**: The report file MUST still be written to the session history exactly as today (the in-terminal render is in addition to, not a replacement for, persisting the report).

### Functional Requirements — Interactive debrief (audio + sync)

- **FR-016**: Before audio starts, the system MUST display a one-line announcement: "🔊 Reading your feedback aloud — press any key to skip."
- **FR-017**: Audio MUST read aloud only the educational parts — the cross-attempt narrative, the top priority, and each grammar pattern's explanation and corrected version — and MUST NOT read transcripts or raw metrics tables.
- **FR-018**: Sections MUST be read in the order: cross-attempt narrative → top priority → each grammar pattern in ranked order.
- **FR-019**: While a section is being read, that section MUST be visually highlighted so the user can follow along, and a progress indicator (e.g. "3 of 6 sections") MUST be visible.
- **FR-020**: Any keypress during the announcement or during playback MUST immediately stop remaining audio and jump to the menu, with no confirmation prompt.
- **FR-021**: The system MUST provide a `--no-audio` flag (or equivalent) that skips audio entirely and goes straight to the visual debrief and menu.
- **FR-022**: All audio MUST be produced via the existing text-to-speech engine.

### Functional Requirements — Menu and replay loop

- **FR-023**: After audio completes or is skipped (or immediately, under `--no-audio`), the system MUST present a menu offering replay (same question), new (pick another question), and quit.
- **FR-024**: The menu MUST accept both single letters (r/n/q) and full words (replay/new/quit), MUST default to replay, MUST support arrow-key navigation, and MUST treat Enter on the default as choosing replay. The menu MUST additionally accept a transcript-toggle key (e.g. `t`) that expands/collapses full transcripts in-place (per FR-014) without leaving the menu.
- **FR-025**: Choosing replay MUST loop back to the listen phase for the same question, run a fresh 4/3/2 cycle, write a new report, and present the debrief again — all with no model reload.
- **FR-026**: On replay the screen MUST clear and go straight to the listen phase: no progress bars, no "Loading models…", and no doctor pre-check (those occur only at launch).
- **FR-027**: Choosing new MUST open the question picker; choosing quit MUST return cleanly to the shell.

### Functional Requirements — Degradation and onboarding

- **FR-028**: If the grammar (LLM) model is not installed, the debrief MUST still run on available Phase-B content and replace the grammar patterns section with the single line "Grammar pattern analysis is available when the LLM model is installed."
- **FR-029**: If audio fails for any reason, the visual debrief MUST continue and the menu MUST appear immediately — the system MUST NOT hang waiting on audio.
- **FR-030**: On the user's very first debrief (no previous reports in the session history), the system MUST show one orientation line above the report: "This is your feedback. I'll read the key parts aloud, then you can replay this question or pick a new one." Returning users MUST NOT see this line.

### Functional Requirements — Compatibility

- **FR-031**: The persisted report file MUST remain compatible with the existing `schema_version: 1` frontmatter; any new fields MUST be additive, and existing fields/consumers (e.g. the trends reader) MUST continue to work unchanged.
- **FR-032**: The feature MUST operate fully offline with no cloud APIs and MUST run within the resources of the target M3 Pro 18 GB hardware.

### Key Entities

- **Grammar pattern (enhanced)**: A detected error with a catalog label, an impact rank, a one-line transfer-reason explanation, and one or more evidence items each carrying the user's verbatim words and a concrete corrected version. Extends the existing pattern entity (label, occurrence_count, evidence quotes, suggested_fix) additively.
- **Cross-attempt narrative**: A short prose summary of change across the three attempts plus a single designated "top priority" for the next session.
- **Debrief view model**: The set of presentable sections derived from a written report — narrative, top priority, ranked pattern cards, attempt summary with trend colouring, collapsed transcripts — and which of them are eligible for read-aloud.
- **Persian-L1 error catalog**: The seed set of error categories with, per category, the label, the learner-facing transfer reason, and the impact weighting used for ranking; extensible via the open-bucket mechanism.
- **Debrief menu choice**: The user's selection among replay / new / quit driving the post-session control flow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A returning user can identify the single most important thing to fix and start a replay within 90 seconds of the session ending, without opening any other tool.
- **SC-002**: Across a 5-session sample checked against a small human-labelled gold set, 100% of reported grammar patterns have an accurate label and verbatim, coherent evidence (no false labels, no speech-recognition-garble evidence).
- **SC-003**: At least 80% of suggested fixes reference the user's actual words and a concrete corrected version rather than a generic rule.
- **SC-004**: Choosing replay returns the user to the "press space to begin attempt 1" prompt in under 3 seconds, with no model reload.
- **SC-005**: The complete interactive debrief (audio + visual + menu) for a typical 3-grammar-pattern report takes no more than 90 seconds before the menu is actionable.
- **SC-006**: In a usability check, the user reports that hearing the corrected versions read aloud helps them understand what they should have said.
- **SC-007**: With the grammar model absent or audio output failing, 100% of sessions still reach the menu without hanging or dead-ending.

## Assumptions

- "Section count" for the audio progress indicator (e.g. "X of N sections") is the number of educational sections actually present: the cross-attempt narrative, the top priority, and one per ranked grammar pattern.
- The 90-second pacing target measures the automated portion of the debrief (audio playback + render + reaching an actionable menu); time the user voluntarily spends expanding transcripts or re-reading is excluded.
- The human-labelled gold set used to verify SC-002/SC-003 is an internal verification artifact for this feature, not a shipped end-user capability.
- "Improved / flat / worsened" for trend colouring is judged by comparing the first and last attempts (consistent with the existing cross-attempt comparison), with a small tolerance band defining "flat".
- Impact ranking of patterns is produced by the analyzer at report-build time and persisted with the pattern so the renderer and read-aloud order are deterministic and reproducible from the report file.
- The replay loop reuses already-loaded TTS/ASR/LLM engines from the current process; "no model reload" assumes the engines remain resident for the lifetime of the practice session.
- Models, devices, and health checks are validated once at launch (existing `doctor`/preflight behaviour); replay deliberately skips them.
- The first-time-vs-returning distinction is based on the presence of any prior report in the existing session-history location.

## Out of Scope

- Pronunciation assessment, computer-assisted pronunciation training, or phoneme-level feedback.
- Any change to the speech-recognition engine.
- New question-authoring UX.
- Changes to the trends dashboard.
- Persistent user preferences (e.g. "always skip audio") — deferred to a future version.
