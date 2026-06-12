# Feature Specification: Pronunciation Drills

**Feature Branch**: `016-pronunciation-drills`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: "Add an optional read-aloud pronunciation-drill stage to the practice loop, so the user trains pronunciation during the otherwise-idle time while their spoken-answer feedback is generated, and receives a pronunciation report appended to the session report. Resource-aware and engine-aware; never risks overloading the machine; additive only."

## Overview

Today, after the user finishes their three timed spoken-answer attempts (the 4/3/2 loop), the
tool spends up to a minute generating grammar/coaching feedback. With a cloud feedback engine
that wait is **dead time** — the user stares at a spinner. This feature fills that dead time
with **read-aloud pronunciation drills**: the tool shows a known target sentence, the user reads
it aloud, and the tool scores the user's pronunciation **against the known text** and gives
short, honest, segment-level feedback ("that /w/ sounded off — round your lips"). A new
**Pronunciation** section is appended to the session report.

Because the pronunciation model is a heavy local model (~1.3 GB on disk, ~2–3 GB peak in
memory), the feature is built around a **resource-aware, engine-aware safety gate**: it will
*never* load the pronunciation model when doing so could exhaust the machine's memory (for
example, when the local feedback model is already resident). Drills are strictly **opt-in**, the
model is downloaded only on first opt-in, and a user who never uses drills downloads and runs
nothing extra.

Scoring is reliable only when the target text is **known** (read-aloud). Scoring the user's
spontaneous interview answers is explicitly out of scope (see Out of Scope / Future).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Train pronunciation during the feedback wait (Priority: P1)

A learner using a **cloud feedback engine** (OpenRouter or Claude Code) finishes their three
attempts. While the cloud grammar/coaching call runs in the background, the tool offers a short
block of read-aloud drills. The learner reads each target sentence aloud at their own pace; the
tool scores it and tells them which sounds were off, with a one-line articulatory tip, and offers
a targeted minimal-pair drill for a recurring error. When both the drills and the feedback are
finished, the combined report (grammar/coaching **plus** a new Pronunciation section) is shown.

**Why this priority**: This is the core value — turning idle feedback-wait time into
pronunciation practice and adding a pronunciation dimension to the report. Without it, the
feature does not exist. It is inseparable from US3 (the safety gate), because the drills may only
be offered when loading the model is safe.

**Independent Test**: With a cloud engine active and adequate free memory, run a full session and
confirm: (a) the drill block is offered after the attempts; (b) reading a sentence containing a
known hard contrast (e.g. "wrapper") with a deliberate error flags the intended sound; (c) the
final report contains a Pronunciation section; (d) the report is shown only after *both* the
feedback and the drills complete.

**Acceptance Scenarios**:

1. **Given** a cloud feedback engine is active and free memory is sufficient, **When** the user
   finishes their three attempts, **Then** the tool offers the read-aloud drill block with a
   simple yes/no prompt, noting drills are available because the local feedback model is not
   resident.
2. **Given** the user accepts the drills, **When** the drill block runs, **Then** the feedback
   call(s) run concurrently in the background and the combined report is shown only after **both**
   the feedback and the drill block have finished.
3. **Given** the user reads a target sentence aloud, **When** a sound is mispronounced relative to
   the known target text, **Then** the tool reports that the sound was off (detection), offers a
   short articulatory tip, and may present a follow-on minimal-pair drill for that contrast.
4. **Given** the user takes longer on the drills than the feedback takes, **When** the feedback
   finishes first, **Then** the tool waits for the user to finish the drills before showing the
   report (the drill block is user-paced, never cut short by feedback latency).

---

### User Story 2 - A calibrated, honest pronunciation report section (Priority: P2)

After a session with drills, the learner opens (or sees the closing summary of) the report and
finds a **Pronunciation** section that summarises the drill results. The feedback **leads with
detection** ("this sound was off") and presents any specific **diagnosis** ("/w/ heard as /r/")
as a *suggestion*, never as a confident verdict — so the learner is never misled by an unreliable
guess.

**Why this priority**: The report is the durable artifact of every session. The pronunciation
results must be honestly framed (detection is reliable; phone-level diagnosis is not) so the
learner trusts the tool and is not sent down the wrong correction path. It depends on P1 producing
drill results.

**Independent Test**: Given a session whose drill results include both a clearly-detected error
and a low-confidence diagnosis, render the report and confirm the Pronunciation section states the
detection plainly and labels the diagnosis as a suggestion ("likely", "may be"), never as a fact.

**Acceptance Scenarios**:

1. **Given** a drill where a sound was confidently off but its specific substitution is uncertain,
   **When** the report renders, **Then** the section states the sound was off (detection) and
   either omits the specific substitution or presents it explicitly as a suggestion.
2. **Given** a session that produced no pronunciation drills (drills off/declined/skipped),
   **When** the report renders, **Then** no Pronunciation section appears and the rest of the
   report is byte-for-byte identical to a pre-feature report.
3. **Given** a session with drills, **When** the report renders, **Then** the grammar, coaching,
   coverage, and all other existing sections are unchanged in content and order.

---

### User Story 3 - Resource-aware, engine-aware safety gate (Priority: P1, inseparable from US1)

A learner using the **local Qwen feedback engine** (the heaviest configuration) finishes their
attempts. The tool detects that loading the pronunciation model on top of the resident local
feedback model would likely exhaust memory and freeze the machine, so it **does not** load the
model. Instead it explains, in plain language, *why* drills are skipped and how to enable them
(e.g. switch to a cloud feedback engine). A learner who truly insists can force the drills on,
but only after an explicit "this may freeze your machine" warning.

**Why this priority**: This is the heart of the feature. The whole point is to add pronunciation
practice **without ever putting the user's machine at risk**. A version of US1 that silently
loaded a 2–3 GB model whenever drills were enabled would be unacceptable. The gate is what makes
US1 safe to ship.

**Independent Test**: Simulate the local-Qwen engine (and/or low free memory); confirm the drills
are declined by default with a plain-language reason and a remediation hint, and that the
pronunciation model is **never loaded**. Separately, exercise the explicit override and confirm it
surfaces a freeze warning before proceeding.

**Acceptance Scenarios**:

1. **Given** the local Qwen feedback engine is active, **When** the drill stage is reached with
   the default setting, **Then** the tool skips the drills, explains that adding the pronunciation
   model to the resident local model would likely exceed memory, and suggests switching to a cloud
   engine — and the pronunciation model is not loaded.
2. **Given** free system memory is below the safe threshold (regardless of engine), **When** the
   drill stage is reached, **Then** the tool skips the drills with a plain-language low-memory
   reason and does not load the model.
3. **Given** the gate would skip the drills, **When** the user has explicitly requested an
   override, **Then** the tool shows a clear "this may freeze your machine" warning before loading
   the model, and proceeds only on explicit confirmation.
4. **Given** the persisted drill setting is `off`, **When** any session runs, **Then** no gate
   check, no offer, and no model load occur.

---

### User Story 4 - Opt-in download through the existing resilient flow (Priority: P2)

The first time a learner opts into drills, the tool discloses the pronunciation model's size and
asks for consent, then downloads it using the **same resilient downloader** used for every other
model (parallel, resumable, sleep-preventing). A learner who never opts into drills never
downloads the model.

**Why this priority**: Honest size disclosure, resumability on flaky internet, and a single
consistent download path are project promises (informed-consent install; resumable downloads). A
bespoke or silent download would violate them. It supports P1 (the model must be present before
drills run) but is not itself the core value.

**Independent Test**: With drills never used, confirm no extra model is downloaded and `doctor`
reports the model as optional/absent without failing. On first opt-in, confirm the standard
consent prompt (with size) appears and the standard resilient download path is used (not a
separate or direct path), and that an interrupted download resumes rather than restarting.

**Acceptance Scenarios**:

1. **Given** drills have never been used, **When** the user runs normal sessions, **Then** the
   pronunciation model is never downloaded and its absence never fails a session.
2. **Given** the user opts into drills for the first time and the model is absent, **When** the
   download is offered, **Then** the model's size is disclosed and consent is requested before any
   bytes are fetched, through the same resilient downloader used for the other models.
3. **Given** a partially-completed pronunciation-model download, **When** the download is retried,
   **Then** it resumes from where it left off rather than restarting from zero.
4. **Given** the user declines the download, **When** the prompt is dismissed, **Then** the
   session continues normally without drills and without error.

---

### User Story 5 - Discoverable docs (Priority: P3)

A learner reading the README/quickstart finds a short section explaining the pronunciation-drill
mode: what it does, that it is opt-in and gated by engine + memory, and how to turn it on/off.

**Why this priority**: Discoverability and correct expectations. Lowest priority because the
feature functions without it, but it is required for users to find and understand the gating.

**Independent Test**: Read the README pronunciation section and confirm it states the feature is
opt-in, engine/memory-gated, read-aloud only, and documents the on/auto/off setting and the
override.

**Acceptance Scenarios**:

1. **Given** the README, **When** a user searches for pronunciation, **Then** they find how to
   enable/disable drills, the default behavior, and why drills may be skipped on their machine.

---

### Edge Cases

- **Local model resident → drills requested anyway**: The default never loads the pronunciation
  model alongside the local feedback model. Only the explicit override does, and only behind a
  freeze warning.
- **Memory drops between gate check and model load**: The gate is checked immediately before
  loading; the estimate is conservative (leaves headroom) so a borderline machine errs toward
  skipping rather than freezing.
- **Microphone unavailable / silent read**: A drill with no captured speech is reported as
  "not captured — repeat after the prompt", never as a pronunciation failure; the drill block
  continues.
- **Pronunciation scoring fails for one drill**: That drill degrades to "could not score" and the
  block continues; a total scoring failure leaves the rest of the report intact (no Pronunciation
  section, or an honest "scoring unavailable" note) and never crashes the session.
- **User aborts (Ctrl-C) during the drill block**: The already-completed attempts and any
  finished feedback are preserved and the report is still written; the drill block stops asking
  for more.
- **Feedback finishes long before drills / drills finish before feedback**: Either ordering is
  fine; the report waits for both.
- **Drill download declined**: The session proceeds without drills, no error, and the user is told
  how to enable them later.
- **Resuming an analysis-pending session**: Resuming re-runs only the text feedback over saved
  transcripts; it does **not** re-run drills (there is no saved read-aloud audio), and this is
  stated plainly. Drills are a live-session-only feature.
- **`--listen-only` session**: No attempts, no feedback wait, so no drills are offered.

## Requirements *(mandatory)*

### Functional Requirements

**Drill block (P1)**

- **FR-001**: After the user completes their spoken-answer attempts (and any follow-ups), the
  system MUST, when drills are enabled and the safety gate permits, present a block of read-aloud
  drills from a bundled drill bank.
- **FR-002**: The system MUST run the post-attempt feedback call(s) concurrently in the background
  while the drill block runs, reusing the existing concurrent/background-analysis mechanism rather
  than adding a second one.
- **FR-003**: The drill block MUST be paced by the user; it MUST NOT be cut short because feedback
  finished first, and feedback MUST be allowed to finish before, during, or after the drills.
- **FR-004**: The system MUST present the combined session report only after **both** the feedback
  and the drill block have completed.
- **FR-005**: Each drill MUST score the user's spoken rendering against the **known** target text
  and identify which sound(s)/word(s) were off, with a short articulatory tip per flagged contrast.
- **FR-006**: When a recurring error contrast is detected, the system MUST be able to route the
  user into one or more follow-on minimal-pair drills targeting that contrast (bounded — see
  FR-024).
- **FR-007**: A drill with no captured speech, or a drill that fails to score, MUST degrade
  gracefully (an honest "not captured"/"could not score" note) without aborting the block or the
  session.

**Report section (P2)**

- **FR-008**: The session report MUST gain a Pronunciation section summarising the drill results,
  rendered only when drills produced results.
- **FR-009**: Pronunciation feedback MUST lead with detection ("this sound was off") and MUST
  present any specific phone-level diagnosis ("/w/ heard as /r/") as a suggestion (hedged
  language), never as a confident verdict.
- **FR-010**: The pronunciation data MUST be stored additively (new optional report fields + a new
  body section). The system MUST NOT change the report schema version, make any existing field
  required, or alter any existing report section's content or order.
- **FR-011**: A session that produced no drills MUST yield a report that is byte-for-byte identical
  to a pre-feature report.

**Safety gate (P3)**

- **FR-012**: Before loading the pronunciation model, the system MUST evaluate a safety decision
  from (a) the active feedback engine and (b) the live available system memory, estimating whether
  loading the model (~2–3 GB peak) is safe on this machine.
- **FR-013**: When the decision is SAFE, the system MUST offer the drills with a simple yes/no
  prompt that respects the configured default, briefly noting that drills are available because the
  local feedback model is not resident.
- **FR-014**: When the decision is UNSAFE, the system MUST NOT load the pronunciation model by
  default. It MUST warn the user, explain the reason in plain language (e.g. local engine resident,
  or low free memory), skip the drills, and state how to enable them (e.g. switch to a cloud
  engine).
- **FR-015**: The system MUST provide an explicit override for an UNSAFE decision; the override
  MUST display a clear "this may freeze your machine" warning and proceed only on explicit user
  confirmation.
- **FR-016**: The drill behavior MUST have a persisted default in user configuration with three
  values: `auto` (offer when safe, skip when unsafe — the default), `on`, and `off`. The setting
  MUST be optional with a silent default and MUST follow the project's YAML-only configuration
  convention.
- **FR-017**: When the setting is `off`, the system MUST perform no gate check, no offer, and no
  model load. The user MUST never be forced into drills and MUST never be silently put at risk.

**Opt-in download (P4)**

- **FR-018**: The pronunciation model MUST be downloaded only when the user first opts into drills,
  after disclosing its size and obtaining consent through the existing consent flow.
- **FR-019**: The download MUST go through the project's established resilient downloader (parallel,
  resumable, sleep-preventing, with its single-connection fallback). The system MUST NOT introduce
  a separate or direct download path for this model.
- **FR-020**: Registering the pronunciation model with the downloader MUST be done by extending the
  existing model registry/downloader in place (the model ships a single non-sharded weight file and
  needs an additional metadata file), not by bypassing it.
- **FR-021**: A user who never opts into drills MUST never download the pronunciation model, and the
  model's absence MUST NOT fail any health check that is not specific to drills.

**Offline & additivity (cross-cutting)**

- **FR-022**: After the one-time model download, the drill path MUST make zero network calls; the
  default offline guarantee MUST be preserved. Canonical pronunciations for the bundled drills MUST
  be available offline without any runtime network fetch.
- **FR-023**: The feature MUST NOT change grammar/coaching analysis, their prompts, or their
  outputs in any way; the grammar/coaching report must be identical whether or not drills ran.

**Bounds & docs**

- **FR-024**: The drill block MUST be bounded (a small number of base drills plus a small bounded
  number of follow-on drills) so it cannot run unboundedly.
- **FR-025**: The README/quickstart MUST document the drill mode: what it does, that it is opt-in
  and engine/memory-gated and read-aloud only, and how to enable/disable it (and the override).
- **FR-026**: All user-facing output for this feature MUST be in English.

### Key Entities *(include if feature involves data)*

- **Drill**: One read-aloud item — a known target sentence/phrase, the contrast it exercises (the
  sound pair it targets, e.g. /w/–/r/), and the minimal-pair follow-ons it can spawn.
- **Drill bank**: The bundled, curated set of drills (sentences + targeted contrasts +
  minimal-pair sets + articulatory tips), with the canonical pronunciation of each drill available
  offline.
- **Drill result**: The outcome of one attempted drill — which sound(s)/word(s) were detected as
  off, the suggested (hedged) diagnosis if any, the tip shown, and a captured/not-captured/error
  status.
- **Pronunciation report section**: The additive summary of the drill results in the session
  report, calibrated per FR-009.
- **Drill setting**: The persisted `auto`/`on`/`off` default plus the optional safety threshold.
- **Safety decision**: The SAFE/UNSAFE estimate derived from the active engine and live available
  memory, with a plain-language reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a configuration where loading the model is unsafe (local feedback model active or
  low free memory), the pronunciation model is loaded **0%** of the time under the default setting
  (it is never silently loaded into an at-risk machine).
- **SC-002**: When the configuration is safe and the user accepts, a deliberate known mispronunciation
  of a curated hard contrast (e.g. reading "wrapper" as "rapper") is flagged on the intended sound
  in a spot-check of self-recorded samples (target: the intended contrast is detected in the clear
  majority of a ~20–30 sample self-check).
- **SC-003**: A session that does not run drills produces a report that is byte-for-byte identical
  to the same session before this feature — verified automatically.
- **SC-004**: A user who never opts into drills downloads **0** additional bytes of model weights
  and incurs **0** additional model loads, including at `--help`.
- **SC-005**: The combined report is presented only after both feedback and drills complete — never
  before — for every drills-enabled session.
- **SC-006**: After the one-time opt-in download, a drills-enabled session makes **0** network
  calls on the default path.
- **SC-007**: Every UNSAFE outcome the user sees includes a plain-language reason and a concrete
  remediation hint (verified by reviewing the messages).

## Assumptions

- **Read-aloud only**: Reliable offline pronunciation scoring requires a known target text.
  Scoring the user's spontaneous interview answers is not reliable offline and is out of scope
  (Future). The drills exercise curated, known sentences.
- **Calibration reality**: Segment-level *detection* ("a sound was off") is reliable; specific
  phone *diagnosis* ("which wrong sound") is not (well under ~60% on hard cases). The report
  therefore leads with detection and hedges diagnosis (FR-009). Published accuracy numbers come
  from curated read-aloud corpora and are optimistic for noisy, jargon-heavy real speech.
- **Typical safe configuration**: A cloud feedback engine (OpenRouter or Claude Code) leaves the
  large local feedback model unloaded, so the machine has room for the pronunciation model. The
  typical unsafe configuration is the local Qwen engine, which already occupies most of the memory
  budget. The gate is therefore expected to *offer* drills mostly in cloud-engine sessions and
  *skip* them in local-engine sessions — but the live-memory check is authoritative, not the engine
  label alone.
- **Memory headroom default**: A conservative free-memory threshold (enough to hold the model's
  peak footprint plus headroom) is used and is itself an optional, overridable configuration value
  with a sensible silent default; borderline machines err toward skipping.
- **Canonical pronunciations are bundled**: Because the drill bank is curated and known, each
  drill's canonical pronunciation is prepared at authoring time and bundled with the drill bank, so
  the runtime path needs no network and no general-purpose grapheme-to-phoneme service (which would
  otherwise risk an online resource fetch). A general text-to-pronunciation hook for arbitrary user
  text is a Future item.
- **Device target**: Apple Silicon, ~18 GB unified memory, consistent with the rest of the project.
  The numbers in the gate are tuned for that target.
- **Drills are live-session-only**: They require microphone capture during the session and are not
  reconstructable from saved transcripts, so `resume` does not re-run them.
- **Existing seams reused**: The feature reuses the existing engine selection/persistence, the
  background/concurrent analysis mechanism, the resilient model downloader + consent flow, the
  report assembly, and the recorder + voice-activity capture, rather than duplicating any of them.

## Out of Scope / Future

The following are explicitly **not** in this feature and are recorded as future stages:

- **Prosody / stress / intonation scoring** (pitch, rhythm, "natural intonation").
- **Reference-free assessment of the spontaneous interview answers** (low-confidence
  "this word may be mispronounced" flags on the actual answers, routing into drills).
- **Drills auto-generated from the current question's vocabulary** (drills are a curated bundled
  bank in this feature).
- **General text-to-pronunciation for arbitrary user-supplied target sentences** (the bundled bank
  ships its own canonical pronunciations).
- **Any change to grammar/coaching analysis, the report schema version, or the offline-by-default
  guarantee.**
