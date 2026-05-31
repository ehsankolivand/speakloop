# Feature Specification: Resilient Model Downloads on Slow / Unstable Networks

**Feature Branch**: `007-robust-model-download`

**Created**: 2026-05-31

**Status**: Draft

**Input**: User description: "Replace how speakloop downloads its on-device models so that downloading is fast and reliable on a slow, high-latency, or unstable internet connection. … Use multiple concurrent streams per file; survive drops with byte-range resume and indefinite hands-free retry; keep the machine awake; fetch only the exact files for the selected model; verify before ready. Anonymous download is the default; an optional credential may be supplied via environment or local configuration but is never committed. The set of models per phase, their on-disk locations, the consent prompt (declined-by-default + size disclosure), and the offline-after-download guarantee must NOT change. The implementation should build on the project's existing, already-validated parallel-and-resumable download script."

## Clarifications

### Session 2026-05-31

- Q: When the required external parallel-download tool is not installed on the user's machine, what should happen? → A: Auto-fallback to the existing single-connection `snapshot_download` path, logging a clear one-line warning that downloads will be slower and less resilient; the install still proceeds and post-download validation still gates readiness.
- Q: Where does the optional "local user configuration" credential live? → A: At the Hugging Face CLI's standard location, `~/.cache/huggingface/token` (produced by `huggingface-cli login`); no new speakloop-specific auth file is introduced. Precedence remains env var > this file > anonymous.
- Q: What does the user see on screen during the indefinite-retry loop? → A: A live Rich-style per-model progress bar plus a concise retry status line. On a network drop, the bar is replaced by a single "Connection lost — retrying in Ns" line until bytes start flowing again, at which point the bar resumes from the prior offset. Matches the existing installer's Rich console usage.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Hands-free completion on an unreliable connection (Priority: P1)

A first-time user on a flaky home connection runs the practice CLI, opts into the
model download at the consent prompt, and walks away. The connection drops in and
out repeatedly over the next several hours and the laptop lid is closed for stretches
of that time. When the user comes back, every model is fully downloaded and validated
— without them having to re-run the command, re-confirm consent, or babysit the
process.

**Why this priority**: This is the headline problem. The user's description is
explicit that on an unreliable connection today's downloader leaves the user with
"a download that never finishes." A reliability fix — resume after each drop,
retry indefinitely on the user's behalf, prevent the machine from sleeping mid-run
— is on its own a complete, demonstrable slice of value: downloads that used to
strand the user now eventually succeed, even if they aren't any faster yet. Every
other improvement (speed, optional auth) is meaningful only after the download can
finish at all.

**Independent Test**: Start a multi-gigabyte download on a constrained link; while
it runs, repeatedly cut and restore the network (e.g., toggle Wi-Fi several times)
and let the lid close for a sustained interval; confirm the download finishes
without any manual restart, the final on-disk byte count matches the expected
model size, and post-download validation passes.

**Acceptance Scenarios**:

1. **Given** a download is in progress, **When** the network connection drops, **Then**
   the download pauses, waits for the network to return, and resumes from the byte
   offset it had already received — it does NOT restart any file from zero.
2. **Given** the network is repeatedly unstable for an extended period, **When** retries
   occur, **Then** retries continue automatically (with backoff) and do not give up;
   the user is never asked to re-run the command to finish a partial download.
3. **Given** a download is expected to take multiple hours and the laptop is left
   unattended (lid closed, user idle), **When** the download is in progress, **Then**
   the system does not enter sleep / power-nap during that time, so the download is
   not interrupted by sleep.
4. **Given** the user presses Ctrl-C, **When** the process is interrupted, **Then**
   partial files remain on disk under the model's path, and re-running the install
   resumes (it does NOT re-download bytes that already arrived).

---

### User Story 2 — Substantial throughput on a constrained link (Priority: P2)

A user on a throttled or high-latency connection sees a multi-gigabyte model
download finish in meaningfully less wall-clock time than today's single-connection
download takes on the same link. The user does nothing different — the speedup
comes from the new mechanism using the available bandwidth more effectively.

**Why this priority**: This is the user-visible benefit users will perceive most
quickly. It depends on P1 — speed gains don't matter if the download cannot
complete at all — but once P1 is in place, throughput is the dominant remaining
pain. It is independently testable: time the same model on the same constrained
link, before and after.

**Independent Test**: On a controlled, throttled link (e.g., shaped to a fixed
bandwidth with added latency), download a representative multi-gigabyte model
with today's mechanism and with the new mechanism; confirm wall-clock time
decreases substantially and the achieved throughput is meaningfully closer to the
link's available bandwidth.

**Acceptance Scenarios**:

1. **Given** a constrained link with bandwidth well above what a single connection
   uses, **When** a multi-gigabyte model is downloaded, **Then** the new mechanism
   pulls each large file over multiple concurrent streams and the total wall-clock
   time is substantially less than the same model downloaded over a single stream
   on the same link.
2. **Given** the same model and the same link, **When** the user measures the
   achieved download rate, **Then** the new mechanism's effective throughput is
   meaningfully higher than the prior single-stream baseline.

---

### User Story 3 — Anonymous by default, optional credential for gated cases (Priority: P3)

A user with no Hugging Face account, who has set no environment variables, can
download all default models successfully (these are public). A different user
who is hitting rate limits or who wants to fetch from a private/gated mirror can
supply a credential via an environment variable or local configuration file; that
credential is read at runtime, used only for the model fetch, and never written
into the repository.

**Why this priority**: Today's default flow already works anonymously for public
models, so this is primarily about preserving that "stranger can clone and run"
guarantee under the new mechanism while adding a clean opt-in for users who need
authenticated access. It is the smallest, last slice — and the most additive — but
omitting it would silently regress the public-release readiness baseline.

**Independent Test**: On a machine with no credentials configured, run the download
and confirm all default (public) models complete successfully. Separately, set the
credential via environment variable, confirm it is consumed by the downloader, and
confirm the repository contains no committed copy of the token.

**Acceptance Scenarios**:

1. **Given** no credential is set in the environment or in local configuration,
   **When** the user opts into the default download, **Then** all default public
   models download successfully.
2. **Given** the user has set the credential via the documented environment
   variable, **When** the download runs, **Then** the credential is used for the
   fetch and a download that would have been rate-limited or gated succeeds.
3. **Given** a fresh clone of the repository, **When** the repository is searched
   for credential-looking values, **Then** no real credential is present and no
   placeholder is wired into source as a default.

---

### Edge Cases

- **Download tool is missing on the target system.** The new mechanism builds on
  an external, parallel-and-resumable download tool; what happens when that tool
  is not installed on the user's machine is deliberately deferred to clarification
  / planning (see Functional Requirements).
- **Disk fills during download.** The mechanism must surface the disk-full error
  clearly rather than appearing to hang or silently truncating; partial files
  already on disk should remain so a re-run after freeing space can resume.
- **Upstream model file changes mid-download** (a rare repo update). Post-download
  validation must catch the resulting integrity mismatch and refuse to mark the
  model ready.
- **Credential is set but invalid / expired.** The download must fail with a clear,
  actionable message that names the environment variable / config field, rather
  than retrying forever as if the network were at fault.
- **User cancels (Ctrl-C) mid-download.** Partial files remain; the next run
  resumes; the consent prompt is NOT shown a second time for the same set of
  already-consented models within the same install session.
- **Sleep-prevention is unavailable** (e.g., the wakelock mechanism requires a
  permission the user has not granted). The download must still proceed; the user
  is warned that the machine may sleep mid-download and that resume will still
  work on the next wake.
- **Repository contains alternate weight formats.** Only the files belonging to
  the selected build (e.g., the specific quantisation) are fetched; sibling
  formats in the same repo are not pulled.

## Requirements *(mandatory)*

### Functional Requirements

**Throughput & resilience**

- **FR-001**: System MUST download each large model file over multiple concurrent
  byte-range streams, with concurrency tuned to give a meaningful speedup on a
  bandwidth-limited link without saturating CPU or RAM on the target hardware.
- **FR-002**: System MUST resume from the last received byte offset after a
  network interruption; no file is re-downloaded from zero if any bytes for that
  file are already on disk.
- **FR-003**: System MUST retry transient network failures automatically and
  indefinitely (with backoff) until the download succeeds, without requiring the
  user to re-run the install command.
- **FR-004**: System MUST keep the machine awake (prevent system / display sleep
  and disk sleep) for the duration of a single model-download run, releasing the
  wakelock as soon as the run ends — whether it ended in success, failure, or
  user interruption.
- **FR-005**: System MUST treat non-transient failures (e.g., invalid credentials,
  repository not found, disk full) as immediately surfaced errors with an
  actionable message — these MUST NOT be swallowed by the indefinite-retry loop.

**Correctness & scope**

- **FR-006**: System MUST fetch only the exact set of files belonging to the
  selected model build (one quantisation / one weight format per model), excluding
  alternate or duplicate weight formats in the same upstream repository.
- **FR-007**: System MUST validate each downloaded model against the existing
  validation criteria (presence + byte size, matching today's tolerance) BEFORE
  treating that model as ready; a model that fails validation MUST NOT be marked
  installed.
- **FR-008**: System MUST store each downloaded model at the exact same on-disk
  path the current installer produces (under the existing per-model directory
  layout), so other modules locate models unchanged.
- **FR-009**: The per-phase model set (which models are required for Phase A, B,
  C) MUST be unchanged by this feature.

**Authentication**

- **FR-010**: Default behavior MUST be anonymous: a user who has set no credential
  in the environment or in local configuration MUST be able to download all
  default (public) models successfully.
- **FR-011**: System MUST accept an optional credential supplied via a documented
  environment variable; when set, the credential MUST be used for model fetches.
- **FR-012**: System MUST also accept the credential from the Hugging Face CLI's
  standard local token file at `~/.cache/huggingface/token` (the file produced
  by `huggingface-cli login`); no speakloop-specific credential file is
  introduced. Precedence MUST be: environment variable > `~/.cache/huggingface/token`
  > anonymous. The exact env-var name is settled in the plan.
- **FR-013**: No real credential value, and no project-default placeholder value,
  MAY be committed to the repository at any point — including in source files,
  configuration templates, manifests, tests, or fixtures.

**User-facing experience (preserved invariants)**

- **FR-014**: The consent prompt MUST continue to disclose the total download size
  before any bytes are fetched, and MUST continue to be declined-by-default; this
  feature does NOT change the prompt's wording, options, or default.
- **FR-015**: Once all required models for a phase are present and validated, the
  application MUST make zero network calls for any normal session activity
  (Constitution Principle II); this feature only affects how models are fetched,
  not the offline-after-download behavior.
- **FR-016**: This feature MUST NOT introduce any telemetry, usage upload, crash
  upload, or remote-configuration fetch. The only outbound network use remains
  the model fetch itself.
- **FR-017**: This feature MUST NOT introduce a new top-level user command or
  user-visible feature surface. The user's interaction with the installer
  (`doctor` health check, the consent prompt on first run, the `practice` /
  `trends` commands afterwards) is unchanged.
- **FR-020**: During an active download, the installer MUST display a live
  per-model progress indicator (e.g., a Rich progress bar showing bytes
  received / expected total) on the existing installer console. On a transient
  network failure, the progress display MUST be replaced by a single concise
  status line naming the retry (e.g., "Connection lost — retrying in Ns") and
  MUST resume the progress display from the prior byte offset when bytes start
  flowing again — it MUST NOT reset to zero. Hard errors (FR-005) MUST surface
  as a clearly distinct, non-transient error line.

**Deployment & environment**

- **FR-018**: The target platform is Apple Silicon macOS (per the constitution).
  Behavior is specified on that platform; behavior on other platforms is out of
  scope.
- **FR-019**: When the required external parallel-download tool is not present
  on the user's machine, the installer MUST automatically fall back to the
  existing single-connection downloader, log a single clear warning line that
  names the missing tool and states that downloads will be slower and less
  resilient, and proceed with the install; post-download validation (FR-007)
  still gates whether each model is marked ready. The installer MUST NOT abort
  the run on the missing tool alone.

### Key Entities

This feature is mechanism-only — it does not introduce new persistent data
shapes. It interacts with two existing entities:

- **Model manifest entry**: The existing per-model definition (name, upstream
  repository identifier, expected on-disk byte size, required-for-phase tag, and
  derived local path). This feature MUST NOT change the manifest schema or the
  current entries.
- **Model directory on disk**: The existing per-model directory under the
  installer's models root, into which weights are written and from which
  validation reads. Layout and path derivation are preserved exactly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a link shaped to a representative constrained bandwidth and
  latency (e.g., a multi-megabit link with elevated round-trip time), a
  multi-gigabyte model download completes in substantially less wall-clock time
  with the new mechanism than with today's single-stream download of the same
  model on the same shaped link — measurable on a single-run A/B comparison.
- **SC-002**: With the network repeatedly interrupted during a single download
  run (network cut and restored several times in succession), the download still
  reaches completion without the user re-running the install command, and the
  final on-disk byte counts match each model's expected size within today's
  validation tolerance.
- **SC-003**: A user with no credentials configured (no environment variable
  set, no local credential file) can complete a full first-time install of all
  default models on a normal home connection without authentication errors.
- **SC-004**: During a single sustained download (multi-hour, lid closed, user
  idle), system / display sleep does not occur for the duration of the download;
  sleep behavior returns to the system default as soon as the download run ends.
- **SC-005**: After a successful install, a `practice` session run end-to-end
  produces no outbound network traffic (verified by network capture or
  equivalent), preserving the offline-after-download guarantee.
- **SC-006**: A clone of the repository contains no committed credential value
  and no placeholder credential wired as a default; the credential is consumed
  only at runtime from the environment or local user configuration.

## Assumptions

- **Single-platform scope.** The target is Apple Silicon macOS; the parallel-
  download tool, the sleep-prevention mechanism, and the credential lookup are
  all specified against that platform.
- **Upstream is Hugging Face.** Today's installer fetches from Hugging Face
  repositories named by id; this feature continues to fetch from Hugging Face
  using the same repository ids. No new host is introduced.
- **Existing parallel-and-resumable script is the basis.** The user's brief is
  explicit: this feature builds on the project's already-validated parallel-and-
  resumable download script. The specific tool, its CLI options, and how the
  installer invokes it are decided in the plan, not here.
- **Per-phase manifest is the source of truth.** What gets downloaded for Phase
  A / B / C, the expected sizes, and the local paths are read from the existing
  `installer/manifest.py`; this feature changes the fetch mechanism only.
- **Validation criteria are unchanged.** The current presence + byte-size check
  with its existing tolerance is the gate for "model is ready"; strengthening
  validation (e.g., to hash-based) is out of scope for this feature.
- **Concurrency is bounded, not configurable.** The number of concurrent streams
  per file is chosen by the implementation to suit Apple Silicon macOS hardware
  and typical home connections; exposing it as a user-tunable knob is out of
  scope (Principle XIII: minimal user-facing surface).
- **Indefinite retry is not infinite-in-a-tight-loop.** "Retries indefinitely"
  means retries with backoff continue for as long as the user lets the process
  run; Ctrl-C still cancels, and a hard error (FR-005) still aborts.
- **`doctor` integration is preserved.** Whatever the FR-019 clarification
  decides about a missing parallel-download tool, the `doctor` command remains
  the canonical place to surface installer health to the user.
- **No change to the report pipeline.** This feature does not touch the report
  format, schema_version, or the LLM / ASR / TTS wrappers; it is confined to the
  installer module's download step.
