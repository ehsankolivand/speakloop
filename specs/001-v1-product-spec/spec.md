# Feature Specification: speakloop v1 — local English interview-practice CLI

**Feature Branch**: `001-v1-product-spec`

**Created**: 2026-05-18

**Status**: Draft

**Input**: User description: "speakloop is a CLI tool for non-native English speakers preparing for senior-level software engineering interviews at international companies. The system reads aloud an interview question and an ideal answer with a native accent, then asks the user to attempt their own answer three times under decreasing time pressure (4 minutes → 3 minutes → 2 minutes), then writes an evidence-based feedback report as a Markdown file the user can review later in Obsidian."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Listen to a question and an ideal answer (Priority: P1)

The user opens a terminal, starts speakloop, picks an interview question from their YAML file, and hears the question and its ideal answer spoken aloud in a native English accent. They listen as many times as they want before deciding to attempt an answer (or to close the tool). No microphone, no LLM, and no feedback report are needed at this stage.

**Why this priority**: This is the iterative-delivery MVP. It delivers standalone value (shadowing practice) using only the TTS engine — no ASR, no LLM — and is the foundation every later journey builds on. If only this story shipped, the user could still practice listening and imitation aloud and improve.

**Independent Test**: With a freshly cloned repo, completed first-run setup, and a starter Q&A file, the user runs the practice command, picks a question, presses replay multiple times for both question and ideal-answer audio, and exits without any other module engaged. Value is delivered with TTS alone.

**Acceptance Scenarios**:

1. **Given** speakloop is installed and the TTS model is downloaded, **When** the user starts a practice session and selects a question, **Then** the system speaks the question aloud and then the ideal answer aloud, with clear visual indication of which is which.
2. **Given** the ideal-answer audio has just finished, **When** the user requests replay, **Then** the same audio plays again from the start without re-synthesis delay if a cached audio file already exists for that question.
3. **Given** the user is in the listening phase, **When** they exit before attempting any answer, **Then** no session report is written and no recording artifacts are left on disk.

---

### User Story 2 — Complete a full 4/3/2 attempt loop and receive a feedback report (Priority: P1)

After listening to the question and ideal answer, the user records three spoken attempts at the question with decreasing time pressure: 4 minutes, then 3 minutes, then 2 minutes. After the third attempt the system writes an evidence-based feedback Markdown report under `data/sessions/` that the user can open later in Obsidian. The report focuses on fluency metrics across the three attempts and recurring grammar patterns common to non-native speakers; pronunciation is explicitly excluded in v1.

**Why this priority**: This is the headline feature. Without it, speakloop is a TTS player, not a practice loop. P1 (alongside Story 1) because the user's primary daily ritual depends on the full loop.

**Independent Test**: Starting from a working install with all three models present, the user goes through one full session and afterwards finds a single Markdown report at `data/sessions/YYYY-MM-DD-qXX.md` containing per-attempt fluency metrics, identified grammar patterns with evidence quotes, and a comparison of the three attempts. The report renders cleanly when opened in Obsidian.

**Acceptance Scenarios**:

1. **Given** the user has just heard the ideal answer for a selected question, **When** they confirm they are ready, **Then** the system starts attempt 1 with a visible 4-minute countdown and records their speech.
2. **Given** the user is mid-attempt and time runs out, **When** the countdown hits zero, **Then** the system stops the current recording at that moment and informs the user the attempt has ended.
3. **Given** attempts 1, 2, and 3 are recorded (durations 4, 3, and 2 minutes respectively, or shorter if the user finished early), **When** the system has finished processing, **Then** a single Markdown file is written under `data/sessions/` with YAML frontmatter and a structured body containing fluency metrics per attempt and grammar-pattern feedback.
4. **Given** the user presses Ctrl+C during any attempt or during post-attempt processing, **When** the program exits, **Then** no Markdown report is written for that session and any partial intermediate files are cleaned up.
5. **Given** processing of the three attempts fails partway (for example the LLM cannot produce a report), **When** the program reports the failure, **Then** the raw transcripts of each attempt are still saved to disk so the user does not lose their work, and the system tells the user where to find them.
6. **Given** the report has been written, **When** the user opens `data/sessions/` as an Obsidian vault, **Then** the file renders with proper frontmatter, headings, and any internal links resolve correctly.

---

### User Story 3 — First-run setup with informed consent and resumable downloads (Priority: P1)

A new user clones the repo, runs `uv run speakloop` for the first time, and is walked through one-time setup: which models will be downloaded, their individual sizes and total disk footprint, and explicit consent before any byte is fetched. If their connection drops mid-download, the next run resumes from where it left off rather than restarting from zero.

**Why this priority**: Without this, the tool effectively does not exist for the target user (unreliable internet, privacy-conscious). The constitution names Resumable Downloads and Easy Install as core principles. This must work on first encounter.

**Independent Test**: On a fresh clone with no models cached, the user runs the tool, sees the consent prompt with a list of models and sizes, accepts, watches the download progress, interrupts the network (or the process) mid-download, restarts, and observes the download resuming. Value: setup completes without re-downloading completed bytes.

**Acceptance Scenarios**:

1. **Given** a freshly cloned repo with no models cached locally, **When** the user runs the entry-point command, **Then** the tool displays the list of models it intends to download, per-model size in MB or GB, total disk footprint, and the target location (`~/.speakloop/models/` or its XDG equivalent), and waits for an explicit yes/no.
2. **Given** the consent prompt is shown, **When** the user declines, **Then** no download is initiated, the tool exits cleanly, and no model files are written to disk.
3. **Given** a model download is in progress, **When** the network connection drops or the user kills the process, **Then** the partial file on disk is preserved.
4. **Given** a partial download exists, **When** the user reruns the tool, **Then** the download resumes from the existing byte offset rather than restarting from zero.
5. **Given** all required models are already present on disk and validated, **When** the user runs the tool, **Then** no re-download is attempted and the user is taken directly to the practice loop.

---

### User Story 4 — Review progress across past sessions (Priority: P2)

After several days of practice the user runs a "trends" command and sees a summary across their past Markdown reports: how their fluency metrics have evolved over time, which grammar patterns recur most often, and how many sessions they have completed. The summary is rendered in the terminal and does not require an external tool.

**Why this priority**: Progress visibility is what makes the practice habit compound. It is a strict superset of Story 2 (reads only files Story 2 produced), so it cannot ship before Story 2 — but the user can extract some value from Story 2 alone, so trends is P2 rather than P1.

**Independent Test**: With three or more past session Markdown files in `data/sessions/`, the user runs the trends command and sees per-metric trend lines (or sparklines) and a ranked list of recurring grammar patterns across sessions, with each pattern linked to the sessions in which it appeared.

**Acceptance Scenarios**:

1. **Given** at least one session report exists in `data/sessions/`, **When** the user runs the trends command, **Then** the system displays a summary that includes total sessions completed, date range covered, and aggregated fluency metrics over time.
2. **Given** several reports contain a recurring grammar pattern (for example, missing articles), **When** the trends command runs, **Then** that pattern appears in a top-N list with a count of how many sessions surfaced it.
3. **Given** there are zero reports in `data/sessions/`, **When** the user runs the trends command, **Then** the system displays a helpful empty-state message pointing the user at the practice command, and exits cleanly without error.
4. **Given** a report file in `data/sessions/` has malformed frontmatter, **When** trends runs, **Then** the system skips that file with a warning naming the file and continues with the rest.

---

### User Story 5 — Discover and verify the installation (Priority: P2)

A new user (or a returning user after a system change) wants to confirm the tool works before committing to a practice session. They run `speakloop --help` to see what commands exist, and a health-check command to confirm Python version, model presence, audio input device, and output device are all good.

**Why this priority**: Confidence before commitment. The constitution requires `--help` to work without models. The health-check is what lets the user self-diagnose before contacting the maintainer.

**Independent Test**: On a machine where models have not yet been downloaded, `speakloop --help` runs to completion and prints command summaries. After install, the health-check command runs and prints a checklist of system checks each marked pass or fail, with actionable remediation text for any failure.

**Acceptance Scenarios**:

1. **Given** speakloop is installed but no models have been downloaded, **When** the user runs `speakloop --help`, **Then** help text is printed and the program exits successfully without prompting for downloads.
2. **Given** speakloop is fully installed with all models present, **When** the user runs the health-check command, **Then** the system reports the status of: Python version, presence and integrity of each required model, default audio input device, default audio output device, and writability of `data/sessions/`.
3. **Given** one or more health checks fail, **When** the health-check completes, **Then** each failure includes a one-sentence remediation hint and the process exits with a non-zero status.

---

### User Story 6 — Add or edit personal Q&A content (Priority: P3)

The user wants speakloop to practice on their own experience and target role, not a generic question bank. They open the Q&A YAML file in any text editor, add or edit entries (question, ideal answer, optional tags), save, and on the next session the new content is available to pick. A small starter example file ships with the repo so the user can practice from minute one and copy the format.

**Why this priority**: Personalization is what makes the tool useful for senior-level interview prep. But the starter example file makes it possible to deliver Stories 1 and 2 first without any Q&A editing — so Q&A editing is P3.

**Independent Test**: With only the starter file present, the user runs a session and sees only the starter questions. They edit the YAML, add a new entry, rerun the session, and the new entry now appears as a selectable option. If they save invalid YAML, the next run reports the parse error with a line number and exits cleanly without crashing.

**Acceptance Scenarios**:

1. **Given** the repo has just been cloned, **When** the user starts speakloop, **Then** they can select from the starter example questions without doing any editing first.
2. **Given** the user has added a new question/answer entry in valid YAML, **When** they restart speakloop, **Then** the new entry is listed alongside existing ones.
3. **Given** the user has saved the YAML with a syntax error, **When** they start speakloop, **Then** the tool prints the YAML parser error including the file path and line number, suggests how to fix it, and exits with a non-zero status.
4. **Given** the user has saved an entry that is missing a required field (for example, no ideal answer), **When** they start speakloop, **Then** the tool reports which entry and which field is missing, and either skips that entry or refuses to start the session depending on configuration — the user is told either way.

---

### Edge Cases

- **No microphone available**: During the practice loop (Story 2), if no audio input device is detected the system MUST refuse to start the attempt phase and direct the user to the health-check command. It MUST NOT silently record zero audio.
- **No speaker / muted output**: During the listening phase (Story 1), if no audio output device is available the user is told and the session does not proceed. Detection at session start is acceptable; constant monitoring is not required.
- **Disk full during a session**: If the disk fills while recording an attempt or while writing the report, the system reports the error to the user, stops cleanly, and leaves any partial files in place for the user to recover or delete.
- **Model file present but corrupt**: At session start, models MUST be validated (size or checksum) before use; a corrupt model is treated like a missing model — the user is offered re-download with the same consent flow as first-run.
- **User picks a question with no ideal answer text**: Rejected at parse time (see Story 6) — does not reach the practice loop.
- **User stays silent through an attempt**: The attempt completes when the timer expires; the resulting transcript is empty and the report acknowledges the attempt produced no measurable speech, without crashing or hanging.
- **User speaks past the buzzer**: At the time limit the system stops recording; speech after the buzzer is not captured, and the user is informed the attempt ended.
- **Ctrl+C during listening or between attempts**: No report written, partial recordings deleted, exit code is non-zero so wrapping scripts can detect the abort.
- **Ctrl+C during post-attempt LLM processing**: No report written. Raw transcripts of completed attempts MAY be preserved on disk for user recovery and the user is told where to find them; if so, they are clearly labeled as a transcript-only artifact and not as a session report.
- **Two practice sessions started on the same day for the same question**: Filenames following the `YYYY-MM-DD-qXX.md` convention would collide; the system MUST disambiguate (e.g., by appending a suffix) so the second session does not overwrite the first.
- **Trends command run against a directory that contains non-speakloop Markdown**: Files without the expected speakloop frontmatter are skipped silently (or with a single grouped notice), not surfaced as errors.

## Clarifications

### Session 2026-05-18

- Q: Which tokens count as "filler words" for the filler-word-density metric? → A: Canonical set of 10 tokens — `um, uh, ah, er, hmm, like, you know, I mean, basically, actually` (matches common interview-coaching tool defaults).
- Q: What silence duration counts as a "pause" for pause-derived fluency metrics (MLR, pause distribution)? → A: 250 ms, matching `doc/research_methodology.md` MLR definition.
- Q: How is a self-correction detected for the self-correction-count metric? → A: Deterministic transcript-only heuristic — immediate verbatim repeats plus explicit repair markers (`I mean, sorry, let me rephrase, actually no, what I meant, wait`); no LLM judgment in the per-attempt count.
- Q: What is the v1 L1-transfer grammar-pattern catalog? → A: Seed + open bucket — fixed top-5 seed (3sg-`s` omission, aux-be/aux-do drop, definite-article omission, preposition substitution/omission, possessor-order transfer) PLUS LLM-surfaced "other recurring patterns" when ≥ 2 occurrences across the three attempts.
- Q: How does the catalog handle L1 scope (Persian-specific vs generic)? → A: Always-on, generic labeling — all seed-5 patterns are evaluated for every user; patterns that do not recur in the user's transcripts simply do not appear in the report. No L1 declaration or config required.

## Requirements *(mandatory)*

### Functional Requirements

#### Practice loop

- **FR-001**: System MUST allow the user to select an interview question from the available Q&A content before each practice session.
- **FR-002**: System MUST synthesize the selected question's text into spoken audio in a native English accent and play it through the default output device.
- **FR-003**: System MUST synthesize the selected question's ideal-answer text into spoken audio and play it through the default output device after the question audio.
- **FR-004**: System MUST allow the user to replay the question audio and the ideal-answer audio any number of times before beginning attempts, without re-synthesizing if a cached audio file already exists for that text.
- **FR-005**: System MUST record exactly three spoken attempts from the user, with time budgets of 4 minutes, 3 minutes, and 2 minutes respectively, in that order.
- **FR-006**: System MUST display a visible countdown for each attempt and stop recording automatically when the timer reaches zero.
- **FR-007**: System MUST allow the user to end an attempt early (before the timer hits zero) via a clearly documented key press.
- **FR-008**: System MUST transcribe each of the three recorded attempts into text for downstream analysis.
- **FR-009**: System MUST refuse to start the attempt phase if no microphone input device is available, and direct the user to the health-check command.

#### Feedback report

- **FR-010**: System MUST produce, after a successful three-attempt session, exactly one Markdown report file under `data/sessions/` named according to the `YYYY-MM-DD-qXX.md` convention.
- **FR-011**: Report files MUST contain YAML frontmatter conforming to a stable, versioned schema including at least: schema version, session date, question identifier, question text, per-attempt durations, and per-attempt fluency metric values.
- **FR-012**: Report body MUST include fluency metrics computed across the three attempts and a comparison highlighting changes between attempts.
- **FR-012a**: Filler-word density MUST be computed by counting occurrences of the canonical filler-token set — `um, uh, ah, er, hmm, like, you know, I mean, basically, actually` — per 100 transcribed words, applied identically to all three attempts. Tokens MUST be matched case-insensitively as whole words/phrases (e.g., "like" inside "likely" is not a match).
- **FR-012b**: For all pause-derived fluency metrics (including mean length of run and pause distribution), a "silent pause" MUST be defined as a contiguous stretch of silence of duration ≥ 250 ms, in line with the threshold cited in `doc/research_methodology.md`. The same threshold MUST be used across all three attempts and across the trends command.
- **FR-012c**: The self-correction-count metric MUST be computed deterministically from the transcript text alone, by summing two transcript-visible signals: (a) immediate verbatim repetitions of a token or short token sequence (e.g., "the the", "I I went"), and (b) occurrences of explicit repair markers from the canonical set `I mean, sorry, let me rephrase, actually no, what I meant, wait` (case-insensitive whole-phrase match). The LLM MUST NOT be invoked for this count; LLM analysis is reserved for the grammar-pattern findings in FR-013.
- **FR-013**: Report body MUST identify recurring grammar patterns observed across the user's transcripts, with each pattern accompanied by at least one verbatim quote from a transcript as evidence.
- **FR-013a**: The grammar-pattern catalog for v1 MUST include a fixed seed set of five high-evidence L1-transfer patterns — (1) 3rd-person-singular `-s` omission, (2) auxiliary `be` / auxiliary `do` drop, (3) definite-article (`the`) omission, (4) preposition substitution or omission (e.g., "join to" → "join"), (5) possessor-order transfer (e.g., "line manager of me"). Each seed pattern MUST be checked against every session's transcripts.
- **FR-013b**: In addition to the seed catalog, the report MUST surface any further recurring pattern detected by the LLM whose evidence count is ≥ 2 occurrences across the three attempts of a single session, labelled clearly as an "other recurring pattern" so seed and open-bucket findings are distinguishable in the Markdown.
- **FR-013c**: The seed catalog (FR-013a) MUST be evaluated for every user regardless of L1; the system MUST NOT require, prompt for, or store an L1 declaration. A seed pattern that does not recur in a given user's transcripts MUST simply be omitted from that session's report rather than reported as "0 occurrences".
- **FR-014**: Report MUST NOT contain pronunciation or phoneme-level feedback in v1.
- **FR-015**: Report Markdown MUST render correctly when the `data/sessions/` directory is opened as an Obsidian vault, including frontmatter parsing and any internal links.
- **FR-016**: If a Ctrl+C signal is received at any point before the report is fully written, the system MUST NOT leave a partial Markdown report on disk.
- **FR-017**: System MUST disambiguate report filenames when two sessions for the same question complete on the same date, without overwriting the earlier file.

#### Installation, models, and consent

- **FR-018**: `speakloop --help` MUST execute successfully and print command-line usage even when no models are present on disk.
- **FR-019**: On first run when models are missing, the system MUST display the list of required models with per-model size and total disk footprint, the target installation location, and prompt the user for explicit yes/no consent before initiating any download.
- **FR-020**: If the user declines consent, the system MUST exit cleanly and write no model files.
- **FR-021**: Model downloads MUST be byte-range resumable — interrupted downloads MUST continue from the existing offset on the next run rather than restarting from zero.
- **FR-022**: System MUST validate model files for completeness (e.g., expected size or checksum) before use; a failed validation MUST be treated like a missing model and trigger the consent-and-download flow.
- **FR-023**: System MUST NOT perform any network call after initial model download and validation are complete.

#### Discovery and health-check

- **FR-024**: System MUST expose a health-check command that reports the status of: Python runtime version, presence and validity of each required model, default audio input device, default audio output device, and writability of `data/sessions/`.
- **FR-025**: Each failing health check MUST be accompanied by a short, actionable remediation message.
- **FR-026**: The health-check command MUST exit with a non-zero status when any check fails, so wrappers and CI can detect failure programmatically.

#### Q&A content

- **FR-027**: The repository MUST ship with a starter example Q&A file in YAML so a freshly cloned install has practice content available immediately.
- **FR-028**: The Q&A file MUST be a human-editable YAML file at a documented location, editable with any text editor.
- **FR-029**: On parse failure of the Q&A file, the system MUST print the file path and line number of the error and exit cleanly without crashing.
- **FR-030**: Q&A entries missing required fields MUST be surfaced to the user by entry identifier and field name.

#### Progress / trends

- **FR-031**: System MUST provide a command that reads existing session reports from `data/sessions/` and displays an aggregated progress summary in the terminal.
- **FR-032**: The aggregated summary MUST include total sessions completed, date range covered, fluency metrics over time, and a ranked list of recurring grammar patterns across sessions.
- **FR-033**: The trends command MUST display a helpful empty-state message when no reports exist, and exit successfully (not error).
- **FR-034**: The trends command MUST skip malformed or non-speakloop Markdown files without aborting.

#### Privacy, locality, and language

- **FR-035**: All audio recordings, transcripts, and report files MUST be written only to the user's local filesystem; no code path may upload, mirror, or transmit them to a third party.
- **FR-036**: All user-facing text (prompts, reports, errors, help) MUST be in English.
- **FR-037**: The system MUST function entirely without internet connectivity once initial model download and validation are complete.

### Key Entities *(include if feature involves data)*

- **Question**: A single interview prompt the user practices. Attributes: stable identifier, question text, ideal-answer text, optional tags (topic, difficulty, role). Source of truth is the user's YAML file.
- **Practice Session**: A single execution of the 4/3/2 loop for one Question on one date. Attributes: date, question identifier, three attempt records, derived metrics, derived grammar-pattern findings.
- **Attempt**: One recorded answer within a session. Attributes: ordinal (1st/2nd/3rd), time budget (4/3/2 minutes), actual duration, recorded audio (transient or discarded after transcription, per privacy posture), transcript text, fluency metric values for this attempt.
- **Session Report**: The Markdown artifact written under `data/sessions/`. Attributes: filename (per `YYYY-MM-DD-qXX.md`), YAML frontmatter (schema-versioned), body sections (per-attempt metrics, comparison across attempts, grammar-pattern findings with evidence quotes).
- **Model**: A locally-stored AI model the system depends on (TTS, ASR, LLM in v1). Attributes: name/identifier, expected on-disk size, validation status, installation path under the user's model directory.
- **Q&A File**: The user-editable YAML document that holds all Questions. Attributes: file path, list of Question entries, schema version.
- **Grammar Pattern Finding**: An aggregated observation across attempts and across sessions. Attributes: pattern label (e.g., "missing articles before singular count nouns"), occurrence count, evidence quotes drawn from the user's transcripts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can clone the repo, run the tool, complete first-run setup, and reach the practice menu in under 30 minutes on a typical home connection (excluding the time spent downloading the model bytes themselves).
- **SC-002**: An interrupted model download resumes from the existing on-disk byte offset on the next run, downloading no more than 1% of already-completed bytes again (allowing for a small safety re-read at the resume point).
- **SC-003**: A completed practice session produces its Markdown report within 60 seconds of the third attempt ending, on the target Apple Silicon hardware.
- **SC-004**: 100% of completed three-attempt sessions produce a Markdown report that opens cleanly in Obsidian without manual frontmatter repair.
- **SC-005**: 0% of aborted sessions (Ctrl+C before the report is fully written) leave a Markdown report on disk for that session.
- **SC-006**: `speakloop --help` returns within 2 seconds on a machine with no models downloaded.
- **SC-007**: The health-check command surfaces every failing precondition (missing model, missing mic, missing speakers, non-writable session directory) in a single run with remediation text for each — verified by deliberately breaking each precondition and confirming it is reported.
- **SC-008**: After 10 completed sessions on different questions, the trends command summarizes all 10 in a single terminal screen (≤ 60 lines of output) and ranks at least the top 5 recurring grammar patterns.
- **SC-009**: 100% of network calls observed during normal use occur during the initial model download flow; no network call is made on any subsequent run once models are validated — verified by running with network disabled after first install.
- **SC-010**: A user who completes one session per day for 14 consecutive days can see, via the trends command, a visible trajectory of their fluency metrics across those 14 sessions (i.e., the chart or list spans 14 distinct entries).

## Assumptions

- **Starter example Q&A**: A small starter file (on the order of 3–5 questions covering common senior-level topics such as system design, behavioral, and technical deep-dives) ships with the repo so the user can practice immediately. The user replaces or extends it with their own questions.
- **Single-user, single-machine**: One human uses one local install on one Apple Silicon Mac. No multi-user accounts, no cross-device sync.
- **Native accent**: "Native English accent" means a single TTS voice that sounds natively American or British; the choice is the engine's responsibility, not the spec's. The user does not pick the accent in v1.
- **Time-pressure stop**: When the per-attempt timer hits zero, the recording is cut at that instant. There is no grace period or auto-extension.
- **Async model**: There is no real-time spoken dialogue. The user finishes speaking, then the system processes and writes a report. The LLM never speaks back to the user.
- **Fluency metric set**: The fluency metrics are anchored to `doc/research_methodology.md`. Numeric definitions encoded in this spec (per the 2026-05-18 clarification session): canonical filler-token list (FR-012a), 250 ms silent-pause threshold (FR-012b), and deterministic self-correction heuristic (FR-012c). The same metric set MUST be applied consistently across all three attempts and the trends command.
- **Persian-L1 emphasis is a default, not a hard wiring**: The methodology research focuses on Persian-L1 patterns, but the v1 seed catalog (FR-013a) is evaluated for every user without an L1 declaration (FR-013c). Patterns that do not recur in a given user's transcripts simply do not appear in their report.
- **Recorded audio is transient by default**: After transcription, raw recorded audio files MAY be deleted to respect disk usage and privacy. Transcript text is preserved as part of the session record. The exact retention policy is a planning decision.
- **Model source**: HuggingFace Hub is the assumed source for resumable downloads, in line with the constitution's guidance.
- **Out of scope for v1**: Pronunciation feedback, phoneme-level scoring, GUI, mobile, cloud sync, multi-user accounts, voice cloning, real-time conversation, cross-platform binaries beyond macOS arm64, auto-update mechanisms — all per user input.
- **Constitution alignment**: Modular boundaries, swappable engines, offline-first behavior, Obsidian-compatible report layout, Apple Silicon target, and resumable downloads are governed by the project constitution at `.specify/memory/constitution.md` and are intentionally not re-stated as functional requirements here, except where a user-visible behavior (consent prompt, --help without models) is required.

## Dependencies

- **`doc/research_methodology.md`**: The authoritative reference for the practice methodology (shadowing, 4/3/2 task repetition, error-tagged feedback, L1-transfer patterns). The Functional Requirements covering fluency metrics and grammar-pattern detection (FR-012, FR-013) resolve their specifics against this document. The constitution (Principle X) requires this file to exist; at spec time it was referenced in the user's intent but not yet present in `doc/`. It was authored before the implementation plan for the feedback module was finalized and is the source of the 250 ms pause threshold (FR-012b) and the seed-5 grammar-pattern catalog (FR-013a).
- **`doc/research_tts.md`**, **`doc/research_asr.md`**, **`doc/research_llm.md`**: Already present in `doc/`; these inform engine choice for the TTS, ASR, and LLM modules respectively. The spec does not name specific engines.
