# Feature Specification: Engine-Aware Onboarding

**Feature Branch**: `015-engine-aware-onboarding`

**Created**: 2026-06-12

**Status**: Draft

**Input**: User description: "Improve onboarding and day-to-day usability of speakloop for people who clone the repo, so a new user goes from `git clone` to a working practice session quickly, can pick and persist their feedback engine without re-typing flags, and can add their own questions cleanly."

## Overview

speakloop now ships three feedback engines — the local Qwen model, OpenRouter (cloud),
and the local Claude Code CLI — but onboarding has not kept pace. Three concrete gaps
exist in the current code:

1. **The local feedback model is never fetched.** `practice` only ever provisions the
   speech and transcription models (TTS + ASR). There is no command that downloads the
   large local feedback LLM, even though `local` is the *default* engine — so a fresh
   clone that keeps the default silently produces sessions with no grammar feedback.
2. **The engine cannot be chosen once.** A default-engine setting exists in the loop
   config file, but nothing writes it; selecting a non-default engine means re-typing a
   flag on every run.
3. **`doctor` mis-reports readiness.** It marks the local feedback model as a hard
   failure even for users who deliberately chose a cloud engine and will never need it.

Adding questions is also harder than it should be: the only documented path is
hand-editing a large shipped YAML file, with no template, no validator, and the
file-precedence rules buried in the README.

This is a **usability/onboarding sprint**. It MUST NOT change analysis quality, the
analysis prompts, the report schema, or the offline-by-default guarantee. Every change
is about the path *to* a working session and the day-to-day ergonomics around it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose and persist a feedback engine, and only download what it needs (Priority: P1)

A new user clones the repo and decides how they want feedback generated. They pick an
engine **once** and the tool remembers it; from then on `practice` uses that engine with
no flags. Setup downloads only the models that engine needs: speech and transcription are
always fetched (they always run locally), but the multi-gigabyte local feedback model is
fetched **only** if the chosen engine is the local one. A user who picks a cloud engine is
never pushed through the large local-model download. They can confirm the tool is ready —
and see exactly what to fix if it is not — before spending time on a session.

**Why this priority**: This is the headline onboarding fix. Without it, a default clone
either wastes bandwidth on a model the user will not use, or silently gives no feedback
because the needed model was never fetched. It unblocks "clone → working session quickly"
and removes per-run flag friction. It is independently valuable even if P2/P3 never ship.

**Independent Test**: Configure each engine as the default in turn and confirm that (a)
the choice persists across runs without flags, (b) an explicit flag on a single run still
overrides the persisted default, (c) selecting a cloud engine never triggers the local
feedback-model download while still fetching speech + transcription, (d) selecting the
local engine does fetch the local feedback model, and (e) `doctor` names the active engine
and reports its readiness with an actionable next step.

**Acceptance Scenarios**:

1. **Given** a fresh clone with no persisted engine, **When** the user runs the setup
   command and selects the local engine, **Then** the choice is saved to the YAML config,
   speech + transcription + the local feedback model are provisioned (with size disclosure
   and consent), and a readiness summary confirms the tool is ready.
2. **Given** a fresh clone, **When** the user runs setup and selects a cloud engine
   (openrouter or claude), **Then** the choice is saved, only speech + transcription are
   provisioned, the large local feedback model is **not** downloaded, and the summary
   states the next step for that engine's credentials.
3. **Given** a persisted default engine, **When** the user runs `practice` with no engine
   flag, **Then** the persisted engine is used.
4. **Given** a persisted default engine, **When** the user runs `practice` with an explicit
   engine flag, **Then** the flag wins for that single run and the persisted default is
   unchanged.
5. **Given** the local engine is active and its feedback model is absent, **When** the user
   starts a full `practice` session, **Then** they are offered the local feedback-model
   download; if they decline, the session still records and saves a resumable report
   (speech + transcription succeed; grammar feedback is left pending) rather than aborting.
6. **Given** a cloud engine is active, **When** the user runs `doctor`, **Then** the local
   feedback model being absent is reported as "not required for the active engine" and does
   **not** fail the health check; the cloud engine's own requirements (credentials/binary)
   are reported instead.
7. **Given** any active engine, **When** the user runs `doctor`, **Then** the output names
   the active engine, whether its requirements are satisfied, and the exact next step for
   anything missing.

---

### User Story 2 - Add and validate your own questions cleanly (Priority: P2)

A user wants to practice with their own questions. Instead of reverse-engineering the
schema from a large shipped file, they get a clear, commented template to start from, a
way to check their file and receive **specific** errors (which entry, which field, what is
wrong) before a session, and a discoverable explanation of which file the tool will
actually use. The existing precedence (explicit path → personal home file → in-repo
default) and the "nothing is created in your home directory unless you put it there"
guarantee are preserved exactly.

**Why this priority**: It removes the main friction in day-to-day use after onboarding —
authoring questions — but a user can still practice with the shipped set without it, so it
ranks below P1.

**Independent Test**: From a clean checkout, obtain the template, save a small question
file, run the validator against it and against a deliberately broken file, and confirm the
valid file passes while the broken file is rejected with a message naming the offending
entry and field. Confirm a discoverability command explains the precedence and reports
which file is currently active, and that nothing was written into the home directory by any
of these steps.

**Acceptance Scenarios**:

1. **Given** a user who wants to start a question file, **When** they request the template,
   **Then** they receive a valid, commented starter question set they can save and edit,
   and the tool does not auto-create any file on their behalf.
2. **Given** a syntactically or schematically invalid question file, **When** the user
   validates it, **Then** the tool reports the precise problem — the file location, the
   offending entry id (or index), and the field — and exits non-zero.
3. **Given** a valid question file, **When** the user validates it, **Then** the tool reports
   success with the question count and any non-fatal warnings, and exits zero.
4. **Given** a user unsure which question file is in effect, **When** they ask, **Then** the
   tool prints the precedence order and the currently-active file (or states that none is
   found and how to add one).
5. **Given** the existing precedence, **When** an explicit path, a personal home file, and
   the in-repo default all exist, **Then** resolution still follows explicit → home →
   in-repo, unchanged.

---

### User Story 3 - Onboarding docs that match the new flow (Priority: P3)

Someone reading the README/quickstart can follow it end to end on a fresh clone: install,
pick and persist an engine, understand what each engine downloads and needs, run a first
session, and add their own questions — with no step that contradicts the tool's actual
behavior.

**Why this priority**: Docs amplify P1/P2 but depend on them existing; they ship last so
they describe real, shipped behavior rather than intent.

**Independent Test**: A reader follows the README from clone to a first session for each
engine and to adding a question set, and every documented command, flag, and config key
matches the tool's behavior.

**Acceptance Scenarios**:

1. **Given** the README install/quickstart, **When** a new user follows it for a chosen
   engine, **Then** every documented step works and no step downloads a model the chosen
   engine does not need.
2. **Given** the README, **When** a user looks for how to select/persist an engine, how the
   cloud/engine options relate, and how to add and validate questions, **Then** each is
   documented and matches the implemented commands.

---

### Edge Cases

- **Conflicting engine flags**: passing the cloud alias together with a non-cloud explicit
  engine remains an error with a clear message (unchanged behavior).
- **Invalid persisted engine value**: a malformed or unknown engine value in the config
  falls back to the built-in default silently (unchanged loop-config behavior); setup only
  ever writes a known-valid value.
- **Setup with download skipped**: the user can persist an engine choice without triggering
  any download in that invocation (e.g., to configure now and fetch later), and a later run
  provisions what is missing.
- **Local feedback model declined**: declining the optional local feedback-model download
  degrades gracefully to a recorded, resumable session — it never aborts the session and
  never silently falls back to a different engine.
- **Cloud credentials missing at setup**: setup reports the missing credential and the exact
  next step rather than blocking; the existing first-run credential prompt on `practice`
  still applies.
- **Non-interactive setup**: setup is scriptable — the engine can be supplied directly so it
  works without a terminal prompt (for CI/automation), and absent a choice in a
  non-interactive context it does not hang.
- **Validating a missing file**: validating a path that does not exist reports the missing
  file clearly and exits non-zero.
- **Template redirected over an existing file**: the template is emitted to standard output;
  the tool itself never overwrites a file — the user chooses where (if anywhere) to save it.
- **`--help` with no models present**: all new commands work with no models downloaded and
  load no engine packages at import (constitution / existing isolation guarantees).

## Requirements *(mandatory)*

### Functional Requirements

#### Engine selection & persistence (P1)

- **FR-001**: Users MUST be able to set a default feedback engine (one of: local,
  openrouter, claude) once via an explicit command, persisted to the user's YAML
  configuration, so subsequent runs need no engine flag.
- **FR-002**: The persisted default MUST be an optional key with a silent built-in default
  (`local`); absence or an invalid value MUST fall back to that default without error.
- **FR-003**: An explicit engine selection on a single run MUST override the persisted
  default for that run only, without modifying the persisted value.
- **FR-004**: The cloud alias MUST remain an exact alias for the openrouter engine, and the
  documented relationship between it and the explicit engine option MUST be clear and
  consistent; existing flags MUST keep working with no breaking change.
- **FR-005**: The persisted engine value MUST only be written by an explicit user action
  (the setup/selection command); no normal run may auto-create or silently modify the user
  config file.

#### Engine-aware model provisioning (P1)

- **FR-006**: Speech (TTS) and transcription (ASR) models MUST always be provisioned for a
  session regardless of the active feedback engine (they always run locally).
- **FR-007**: The large local feedback model MUST be downloaded only when the local engine
  is the active feedback engine; selecting a cloud engine MUST never trigger its download.
- **FR-008**: First-run setup MUST provision exactly the models the chosen engine needs,
  disclosing each model's size and obtaining consent before any download (existing consent
  + size-disclosure behavior is reused).
- **FR-009**: When the local engine is active and its feedback model is absent, the system
  MUST offer that download as part of starting a full session; declining MUST degrade to a
  recorded, resumable session (speech + transcription still run; grammar feedback pending)
  rather than aborting the session.
- **FR-010**: Provisioning MUST remain resumable and MUST NOT re-download already-present
  models (existing resumable-download behavior is reused).
- **FR-011**: Setup MUST support a mode that persists the engine choice without performing
  any download in that invocation.

#### Doctor readiness reporting (P1)

- **FR-012**: `doctor` MUST report the active feedback engine (from the persisted config,
  or the default).
- **FR-013**: `doctor` MUST report whether the active engine's requirements are satisfied —
  required models present, and for cloud engines whether credentials/binary are configured —
  and MUST give the exact next step for anything missing.
- **FR-014**: `doctor` MUST treat the local feedback model as required only when the local
  engine is active; when a cloud engine is active, its absence MUST be reported informationally
  and MUST NOT fail the health check.
- **FR-015**: `doctor` MUST continue to fail the health check when an always-required model
  (speech or transcription) or a core precondition (e.g. output device, writable sessions
  directory) is missing, and MUST keep listing every model row even on failure.

#### Question authoring & validation (P2)

- **FR-016**: Users MUST be able to obtain a clear, commented question-file template that is
  itself valid against the schema and can be saved and edited as a starting point.
- **FR-017**: Users MUST be able to validate a question file (an explicit path, or the
  currently-resolved file by precedence) and receive either a success summary (with question
  count and any non-fatal warnings) or a specific error naming the file, the offending entry
  (id or index), and the field at fault.
- **FR-018**: Users MUST be able to discover which question file is currently active and the
  full precedence order through the tool itself.
- **FR-019**: The existing question-file precedence (explicit path → personal home file →
  in-repo default) MUST be preserved, and no command in this feature may auto-create a file
  in the user's home directory; the template is emitted to output for the user to redirect.

#### Documentation (P3)

- **FR-020**: The README/quickstart MUST document engine selection and persistence, the
  cloud/engine relationship, engine-aware setup and what each engine downloads/needs, and
  the question template/validation/precedence — matching the implemented commands and keys.

#### Cross-cutting guarantees (all priorities)

- **FR-021**: No change in this feature may alter analysis quality, the analysis prompts, the
  report schema version, or make any report field required.
- **FR-022**: No new network call may be added to the default local path after models are
  downloaded; cloud-engine network use stays confined to the opt-in cloud path.
- **FR-023**: All new commands MUST work with no models downloaded and MUST NOT cause any
  engine package to be imported at CLI import time (existing isolation guarantees preserved).
- **FR-024**: All new user-facing output MUST be in English.

### Key Entities *(include if feature involves data)*

- **Feedback engine selection**: the user's chosen analysis engine — one of local,
  openrouter, claude — stored as an optional key in the user's YAML loop configuration with a
  silent default of local.
- **Engine requirement profile**: the conceptual mapping from an active engine to what it
  needs to be "ready" — always speech + transcription models, plus (local) the local feedback
  model, or (cloud) the relevant credentials/binary.
- **Question-file template**: a canonical, schema-valid, commented example question set used
  both as the authoring starting point and as documentation of the schema.
- **Readiness report**: the per-engine view `doctor`/setup present — active engine, satisfied
  vs. missing requirements, and the next step for each gap.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from a fresh clone to a persisted engine choice plus the
  correct models provisioned for that engine using a single documented setup command, with no
  manual config-file editing.
- **SC-002**: When a cloud engine is selected, the large local feedback model is downloaded
  **zero** times; speech and transcription are still provisioned.
- **SC-003**: After selecting an engine once, a user runs sessions repeatedly with no engine
  flag and the chosen engine is used every time; an explicit flag overrides a single run 100%
  of the time without changing the persisted default.
- **SC-004**: `doctor` states the active engine and a correct readiness verdict for it, and
  does not report a false failure for a model the active engine does not need.
- **SC-005**: For an invalid question file, the validator identifies the offending entry and
  field in 100% of the seeded invalid-fixture cases; for a valid file it reports success and
  the correct question count.
- **SC-006**: The emitted question template loads and validates successfully without edits.
- **SC-007**: No file is created in the user's home directory by any setup, template, or
  validation command unless the user explicitly directs output there.
- **SC-008**: `--help` and all new commands run with no models present and load none of the
  engine packages at import (verified by the existing isolation gates).
- **SC-009**: The full existing test suite passes at no fewer than its pre-feature count, and
  the byte-identical analysis-equivalence, help-without-models, path-portability, and
  context-file-budget gates stay green.
- **SC-010**: A reader can follow the README end to end for each engine and for adding a
  question set with no step that contradicts actual behavior.

## Assumptions

These record the judgment calls made so the spec carries zero open clarifications. They
follow existing project conventions (constitution, root + module CLAUDE.md, prior specs
008/010/011) verified against current code.

- **Setup command shape**: a single explicit onboarding command (working name `setup`) is
  the cleanest fit for "pick an engine once + provision what it needs + report readiness,"
  consistent with the flat command style (`practice`, `doctor`, `today`, …). It accepts the
  engine directly (for scripting) and otherwise prompts; a download-skip mode satisfies
  FR-011. The exact command/flag names are an implementation/plan concern.
- **Persistence location**: the existing optional `engine:` key in the loop YAML config is
  reused as the persisted default — it already exists with a silent `local` default and is
  already read by engine resolution. No new config file or format is introduced (constitution:
  YAML-only user config). Writing it is an explicit, user-initiated action only (FR-005),
  preserving the "never silently create files in home" guarantee.
- **Engine → model mapping**: listen-only needs speech only; a full session needs speech +
  transcription always, plus the local feedback model only when the local engine is active.
  This reuses the existing phased model manifest; cloud engines never reference the local
  feedback model.
- **Graceful local-model decline**: declining the optional local feedback model degrades to a
  recorded, resumable session rather than aborting — consistent with the existing
  graceful-degradation contract (a missing local feedback model already yields a no-grammar,
  resumable report) and constitution Principle XII (partial system stays usable). The
  always-required speech/transcription download keeps its current decline-aborts behavior.
- **Doctor readiness**: doctor gains an engine-aware readiness view and stops treating the
  local feedback model as a hard failure for cloud users. Cloud/claude rows stay non-failing
  (opt-in), matching existing doctor behavior; always-required models and core preconditions
  keep failing the exit code.
- **Question template & validation surface**: validation reuses the existing loader/schema,
  which already yields file:line and entry-id+field errors; the feature exposes them through a
  command and adds a discoverability/precedence view and a canonical template. The template is
  emitted to standard output (never written to home) so the no-auto-create guarantee holds.
- **Credential handling in setup**: setup reports cloud-credential readiness and the next step
  but defers deep, network-dependent validation to the existing first-run credential flow on
  `practice`, keeping setup fast and offline-friendly for the parts that can be.
- **No analysis changes**: prompts, grammar/coaching behavior, report schema, and the
  offline-by-default guarantee are untouched (out of scope, FR-021/FR-022). This feature is
  docs + onboarding/provisioning/reporting ergonomics only.
- **Branch base**: this feature depends on the engine-selection, loop-config, and context-layer
  work from features 010–014, which are integrated on the active development branch but not yet
  on the main branch; it is therefore based on that integration branch (recorded for correct
  merge ordering at handoff).
