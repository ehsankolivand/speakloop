# Feature Specification: Offline Self-Practice Modes — Rescue-Lines Deck & Answer Shadowing

**Feature Branch**: `018-self-practice-modes`

**Created**: 2026-07-08

**Status**: Draft

**Input**: User description: "Add two additive, offline-first self-practice modes to SpeakLoop, both modeled on the existing `speakloop pronounce` standalone-command template … Mode A — Rescue-lines deck (`speakloop deck`, P1) … Mode B — Answer shadowing (`speakloop shadow`, P2) …"

## Overview

Two additive, offline self-practice modes that each turn material the app **already produces** into a spoken rehearsal loop, without an interview session and without writing a session report:

- **Mode A — Rescue-lines deck** (`speakloop deck`): spaced-repetition drilling of the learner's **own corrected lines** (the "Better:" corrections the analyzer already recorded in past reports), plus a small bundled starter set of high-value interview discourse chunks. A self-graded hear → say → see → self-mark loop reschedules each line-card on the app's existing review ladder until it stabilizes. Includes an offline Anki cloze export.
- **Mode B — Answer shadowing** (`speakloop shadow`): fluency and domain-phrasing practice over a question's ideal answer, sentence by sentence — hear it, repeat it, and get deterministic offline feedback on completeness (did the repeat contain the sentence's key words) plus pace and fillers.

Both modes are English-only, CLI-only, and make **zero network calls after the one-time model download**. Both are strictly additive: they leave report `schema_version` at 1 and the derived-store `STORE_VERSION` at 1, keep the store rebuildable from session reports, and require no models to be present for `--help` to work.

## Clarifications

### Session 2026-07-08

Resolved autonomously from the scoped feature intent and the project constitution (this cycle runs without a live reviewer; each answer is encoded into the requirements below).

- Q: Default cap on one `speakloop deck` run, and what happens when nothing is due? → A: Default **20** due cards per run, overridable with `--limit`; when nothing is due, offer to practise ahead by drilling the soonest-due cards up to the cap.
- Q: How does the learner select a question for `speakloop shadow`? → A: An interactive picker (mirroring `practice`), plus a `--question <id>` flag to jump straight to one; `--limit` caps the number of sentences per run.
- Q: Is shadow completeness a pass/fail gate, and how are the sentence's key words matched? → A: **Formative, not pass/fail** — report "covered X of Y key words" and list the missed ones; flag a sentence as *strong* at **≥ 70%** coverage but never block progress. Match on normalized word tokens (lowercased, punctuation-stripped), with function words excluded.
- Q: Does `speakloop deck --export` write only the due cards or the whole deck? → A: The **whole deck** — every derived card plus the starter cards, deduplicated — as a full snapshot, independent of scheduling.
- Q: How many bundled starter cards ship? → A: A fixed, curated set of **at least 8** English-only interview discourse chunks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rescue-lines deck: re-say your own corrected lines on a spaced schedule (Priority: P1)

A learner has completed several practice sessions. The grammar analyzer flagged recurring errors and, for each, recorded what they said ("You said") and the corrected version ("Better:"). Today the learner wants to *drill those corrected lines* — not re-answer whole questions — so the fixes stick and their real interview answers get cleaner.

They run `speakloop deck`. The app gathers the corrected lines from their past reports (deduplicated), mixes in any due bundled starter chunks, and presents the ones due today one at a time. For each card: the app **speaks the corrected line** aloud (they can replay it), the learner **says it themselves**, then the app **shows the target** ("You said …" / "Better: …" / the rule) and asks them to **self-mark** how it went — *again*, *hard*, *good*, or *easy*. That self-mark reschedules the card on the app's existing review ladder: *again* brings it back immediately, *good*/*easy* push it further out, and two strong marks in a row retire it from daily rotation. Their progress persists between runs.

Separately, the learner can run `speakloop deck --export cards.txt` to write the same cards to an offline file that imports into Anki as cloze-deletion cards (the changed word hidden as `{{c1::…}}`, with a short rule hint) — bringing a previously cloud-only convenience to the fully-local path.

**Why this priority**: Re-saying your *own* transfer errors, corrected and spaced, is the single highest-leverage language practice for this user; it closes the loop from "the analyzer found the error" to "you drilled the fix until it stuck." It is fully offline, needs only the speech engine already used for listening, and delivers standalone value even if Mode B is never built.

**Independent Test**: With a set of past session reports (fixtures) containing corrections, run `speakloop deck` and confirm the loop plays the corrected line before prompting, records a self-mark, and reschedules the card; re-run and confirm scheduling persisted. Run `speakloop deck --export` and confirm a valid Anki-cloze file is written. No microphone, network, or models beyond speech synthesis are required, and no session report is written.

**Acceptance Scenarios**:

1. **Given** past reports containing at least one corrected line, **When** the learner runs `speakloop deck`, **Then** each due card is spoken aloud first, then its target is shown, then a self-mark is collected — hear → say → see → self-mark, in that order.
2. **Given** a card the learner marks *again*, **When** the deck is next run, **Then** that card is due again at the shortest interval.
3. **Given** a card the learner marks *good* or *easy* on two consecutive reviews, **When** the deck is next run, **Then** that card has left the daily rotation until the long maintenance interval.
4. **Given** the learner has completed a deck run, **When** they run it again, **Then** the per-card scheduling from the previous run is honored (state persisted between runs).
5. **Given** the learner runs `speakloop deck --export cards.txt`, **When** the command completes, **Then** `cards.txt` contains one cloze card per line with the changed token wrapped in `{{c1::…}}` and a trailing rule hint, and no drilling loop runs.
6. **Given** a brand-new learner with no past sessions, **When** they run `speakloop deck`, **Then** the bundled starter discourse chunks are available to drill so the mode is never empty.
7. **Given** the derived card cache is deleted, **When** it is rebuilt from the session reports, **Then** the same set of cards is reproduced (card content is rebuildable; only the review-scheduling state resets to a placeholder, exactly like the existing question schedule).

---

### User Story 2 - Answer shadowing: rehearse the real answer sentence-by-sentence (Priority: P2)

A learner wants to build fluency and absorb the exact domain phrasing of a strong answer. They run `speakloop shadow` and pick a question. The app splits that question's ideal answer into sentences. For each sentence it **speaks the sentence** (optionally a slower first read), the learner **repeats it**, and the app **transcribes the repeat** and gives immediate, deterministic, fully-offline feedback: **completeness** (which of the sentence's key content words were present in the repeat, and which were missed) plus **pace** (words per minute) and **filler** counts. The learner moves through the answer sentence by sentence, hearing native phrasing and immediately re-producing it.

**Why this priority**: Shadowing is the top fluency/prosody technique in the app's own methodology, and here the material *is* a strong interview answer — so it trains fluency and rehearses interview content at once. It is P2 because it depends on the speech-recognition engine (heavier provisioning) whereas the deck needs only speech synthesis; each mode nonetheless stands alone.

**Independent Test**: With a question whose ideal answer has several sentences, run `speakloop shadow`, confirm each sentence is spoken and the recorded repeat is transcribed and scored for content-word completeness plus pace/fillers, all offline and deterministically for a given transcript, with no report written and no residual audio left on disk.

**Acceptance Scenarios**:

1. **Given** a chosen question, **When** the learner runs `speakloop shadow`, **Then** the ideal answer is split into sentences and each is presented as its own hear → repeat → feedback round.
2. **Given** a sentence and the learner's repeat, **When** the repeat is transcribed, **Then** the feedback names how many of the sentence's key content words were covered and lists the ones that were missed.
3. **Given** the same transcript for a repeat, **When** feedback is computed twice, **Then** the completeness, pace, and filler results are identical (deterministic, no model-in-the-loop scoring).
4. **Given** a sentence containing a dotted non-boundary token (e.g., a version like "API 28" or a camelCase identifier), **When** the ideal answer is split, **Then** the sentence is not broken at that token.
5. **Given** the learner produces no audible repeat (silence), **When** the round is scored, **Then** the app reports that it did not catch a repeat rather than scoring it as a failed attempt, and the learner can continue.
6. **Given** a shadow session ends (finished, quit, or interrupted), **When** the command exits, **Then** no session report is written and no recording remains on disk.

---

### Edge Cases

- **No corrections yet / empty deck**: a learner with sessions but no corrected lines still gets the bundled starter cards; a learner whose deck has nothing due today is told they are caught up (with the option to keep practicing ahead), never shown an error.
- **No-op corrections**: an evidence item whose "Better:" text equals the "You said" text produces no card (mirrors the existing report renderer's skip rule).
- **Duplicate corrections across sessions**: the same corrected line seen in multiple reports collapses to a single card (stable identity), so review history is not fragmented.
- **Unreadable/foreign report files**: a malformed or non-SpeakLoop `.md` in the sessions folder is skipped, never aborting card derivation (same tolerance as the existing store rebuild).
- **Non-interactive invocation** (piped input, no TTY): the self-graded deck loop cannot collect marks, so it is skipped with a clear notice; `deck --export` still works non-interactively.
- **Export to an unwritable path**: the export command reports the failure clearly and exits non-zero without a traceback.
- **Missing / declined models**: if the speech engine(s) a mode needs are absent and the learner declines the download, the mode exits cleanly with guidance to run it again later — no crash.
- **Shadowing a very short answer**: an ideal answer that is a single sentence still yields one valid round.
- **Empty or whitespace-only ASR result** in shadowing: treated as "not captured," not as a completeness failure.
- **Mid-loop quit / Ctrl-C**: both modes stop cleanly at the current card/sentence; the deck persists progress made so far; shadowing leaves no artifacts.

## Requirements *(mandatory)*

### Functional Requirements

#### Shared (both modes)

- **FR-001**: Both commands MUST run fully offline after the one-time model download — no network calls on the practice path.
- **FR-002**: `speakloop --help`, `speakloop deck --help`, and `speakloop shadow --help` MUST succeed with no models present and without loading any speech/recognition/analysis engine.
- **FR-003**: Each mode MUST provision only the engine(s) it needs, through the app's existing consent/download flow, and MUST NOT load the pronunciation phoneme-scoring model.
- **FR-004**: Neither mode may write a session report, and neither may change report `schema_version` (stays 1) or the derived-store `STORE_VERSION` (stays 1).
- **FR-005**: All user-facing output MUST be English only.
- **FR-006**: Any recording either mode makes MUST be deleted after use; no learner audio persists on disk.
- **FR-007**: Declining or failing a required model download MUST end the command cleanly with actionable guidance, never a traceback.
- **FR-008**: Both modes MUST be user-paced and interruptible: the learner can replay the spoken target, advance, and quit at any point.

#### Mode A — Rescue-lines deck (`speakloop deck`)

- **FR-010**: The deck MUST derive its cards from the corrected lines recorded in existing session reports (each "Better:" correction paired with its "You said" quote and the rule that explains it).
- **FR-011**: The deck MUST skip corrections whose corrected text is empty or identical to the original (no-op fixes produce no card).
- **FR-012**: The same corrected line appearing in multiple reports MUST map to a single card with a stable identity, so its review history is not duplicated.
- **FR-013**: The deck MUST include a fixed bundled starter set of **at least 8** high-value interview discourse chunks so a learner with no prior corrections still has cards to drill.
- **FR-014**: For each due card the loop MUST proceed hear → say → see → self-mark: speak the corrected line, let the learner say it, then reveal the target (You said / Better / rule), then collect a self-mark of *again* / *hard* / *good* / *easy*.
- **FR-015**: The self-mark MUST reschedule the card on the app's existing review-interval ladder (poor → shortest, up through strong → longest, with two consecutive strong marks retiring the card to the maintenance interval), and the per-card scheduling MUST persist between runs.
- **FR-016**: The deck MUST present cards that are due (previously scheduled for today or earlier, or never reviewed) in review-priority order (most overdue first) and MUST bound a single run's size, defaulting to **20 cards** and overridable per run via `--limit`.
- **FR-017**: The per-card review state MUST live in a new, default-empty section of the derived store, such that a store lacking the section loads unchanged and a store rebuild reconstructs every card's content from reports (review-scheduling state resetting to a placeholder, exactly as the existing question schedule does on rebuild).
- **FR-018**: The command MUST offer an export mode that writes the **whole deck** (every derived card plus the starter cards, deduplicated — a full snapshot, independent of scheduling) as an offline Anki cloze-import file — one card per line, the changed token wrapped in `{{c1::…}}`, followed by a short rule hint — matching the format the cloud coach already emits, and the export MUST run without drilling and without network access.
- **FR-019**: When run without an interactive terminal, the drilling loop MUST be skipped with a notice (self-marking requires interaction) while export remains available.
- **FR-020**: When nothing is due, the deck MUST tell the learner they are caught up rather than erroring, and allow practising ahead (drilling the soonest-due cards up to the run cap) if they choose.

#### Mode B — Answer shadowing (`speakloop shadow`)

- **FR-030**: The command MUST let the learner select a question from the active question file — via an interactive picker (mirroring `practice`) or a `--question <id>` selector — and split that question's ideal answer into sentences; `--limit` MUST cap the number of sentences drilled per run.
- **FR-031**: Sentence splitting MUST be abbreviation-aware: it MUST NOT break a sentence at dotted non-boundary tokens such as version numbers ("API 28"), decimals, or dotted/camelCase identifiers, and MUST treat blank-line paragraph breaks as boundaries.
- **FR-032**: For each sentence the loop MUST proceed hear → repeat → feedback: speak the sentence (with an option for a slower first read), record the learner's repeat, and transcribe it.
- **FR-033**: The feedback MUST be deterministic and fully offline (no model-in-the-loop scoring): for a given transcript the same feedback is produced every time.
- **FR-034**: The completeness feedback MUST be **formative, not a pass/fail gate**: it MUST report how many of the sentence's key content words the repeat contained ("covered X of Y") and MUST list the missed content words (function words/stopwords excluded), matching on normalized word tokens (lowercased, punctuation-stripped); it MAY flag a sentence as *strong* at ≥ 70% coverage, but MUST never block advancing to the next sentence.
- **FR-035**: The feedback MUST also report pace (words per minute) and filler-word count/density for the repeat, using the app's existing deterministic fluency metrics.
- **FR-036**: A silent or empty repeat MUST be reported as "not captured," distinct from a low-completeness result, and MUST NOT block progressing to the next sentence.
- **FR-037**: Shadowing MUST provision the speech-synthesis and speech-recognition engines only (not the phoneme scorer, no analysis LLM), and MUST write no report and no cross-session data in this version.

### Key Entities *(include if feature involves data)*

- **Line-card (Mode A)**: one drillable corrected line. Content (all rebuildable from reports): the target/corrected text, the original "You said" quote, the rule/explanation, and the source question. Plus review-scheduling state (last mark, current interval, next-due date, consecutive-strong count, mastered flag, review count) — the persisted, live part.
- **Starter card (Mode A)**: a bundled, English-only interview discourse chunk shipped with the app (phrase + the token(s) to cloze + a rule hint) that seeds the deck when the learner has few or no corrections; schedules like any other card.
- **Deck (Mode A)**: the collection of the learner's line-cards + due starter cards, ordered by review priority (most overdue first) and bounded per run.
- **Shadow sentence (Mode B)**: one sentence of an ideal answer, with its set of key content words used to score completeness.
- **Shadow feedback (Mode B, ephemeral)**: per-sentence completeness (covered vs missed key words) + pace + filler counts; shown live, not persisted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A learner with at least one past session containing a correction can begin drilling their corrected lines with zero network calls and without any speech-recognition or analysis model present.
- **SC-002**: A card marked *good* or *easy* twice in a row is not shown in the daily deck again until the long maintenance interval (it leaves active rotation), and a card marked *again* is due at the shortest interval on the next run — verifiable purely from scheduling behavior.
- **SC-003**: Per-card review progress persists across separate `deck` runs (a card advanced in run 1 is scheduled accordingly in run 2).
- **SC-004**: Deleting the derived card cache and rebuilding it from the session reports reproduces the identical set of cards (content is 100% rebuildable from reports).
- **SC-005**: The `deck --export` output is a full-deck snapshot (derived cards + starter cards) that imports into Anki as cloze cards — one per line, the changed word hidden — with every card carrying a non-empty cloze deletion.
- **SC-006**: A brand-new learner with no sessions still has at least the full bundled starter set (≥ 8 cards) available to drill.
- **SC-007**: A learner can shadow any question's ideal answer sentence-by-sentence offline, receiving completeness + pace + filler feedback on every sentence.
- **SC-008**: For a fixed repeat transcript, the completeness result (count covered and the exact list of missed key words) is identical on repeated computation and correctly excludes function words.
- **SC-009**: The sentence splitter keeps version numbers and dotted/camelCase identifiers intact (no sentence is broken at "API 28", a decimal, or an identifier containing a dot).
- **SC-010**: A completed or interrupted `shadow` run writes no session report and leaves no learner recording on disk.
- **SC-011**: `speakloop --help` and both new commands' `--help` succeed with no models downloaded and load no speech/recognition/analysis engine (verifiable by the existing import-isolation guard).
- **SC-012**: Adding these modes leaves a report produced without them byte-identical to before, and a derived store that predates them loads without change (`schema_version` and `STORE_VERSION` both remain 1).

## Out of Scope *(this cycle — noted future extensions)*

- **Mode A — ASR auto-scoring of the spoken line**: v1 is **self-graded** (hear → say → see → self-mark). Automatically transcribing and grading the learner's spoken card is a deliberate future extension; it would add the recognition engine that the self-graded deck intentionally avoids.
- **Mode B — phoneme scoring of arbitrary sentences**: v1 gives **content-word completeness + pace/fillers only**. Per-word pronunciation scoring of arbitrary ideal-answer sentences (via a synthesized self-reference) is a noted future extension requiring threshold recalibration and per-word attribution work.
- **Mode B — cross-session persistence**: v1 is **ephemeral** (writes nothing). A cross-session tally of chronically-mangled sentences to bias future shadow rounds is a noted future extension.
- **Coach-card parsing**: Mode A cards derive from the structured grammar-evidence in reports, which is fully rebuildable. Parsing the cloud coach's free-form Markdown cards (which are not machine-structured and do not round-trip through the report parser) is out of scope.

## Assumptions

- **Card source of truth is the structured grammar evidence** ("You said"/"Better:"/rule) already stored in every report, so cards are fully reconstructable from reports and the store stays a pure cache.
- **The self-mark maps onto the existing four-level review grade** (again→lowest … easy→highest), so the existing interval ladder is reused unchanged as the single tuning surface rather than a new scheduling scheme.
- **Neither mode needs the pronunciation phoneme-scoring model**, so neither needs that model's memory-safety gate; each provisions only the engines it uses via the existing consent flow (the deck: speech synthesis only; shadowing: synthesis + recognition), matching listen-only practice, which has no special gate.
- **The active question file is resolved by the app's existing precedence** (personal override → repo default), and shadowing operates on whatever that resolves to.
- **Content words for shadowing** are the sentence's tokens minus a standard English function-word/stopword set; short function words are intentionally not required in the repeat.
- **A "sentence" for shadowing** is a reasonable prose sentence; the ideal answers are clean, sentence-terminated prose (no need for a full NLP sentence tokenizer), and paragraph breaks reinforce boundaries.
- **Bundled starter cards are shipped English-only content**, validated the same way other bundled content is, and are few in number (a curated handful).
- **These features target Apple Silicon** like the rest of the app; performance budgets assume the resident engines already used by `practice`/`pronounce`.
