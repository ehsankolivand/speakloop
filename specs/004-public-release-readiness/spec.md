# Feature Specification: Public Release Readiness

**Feature Branch**: `004-public-release-readiness`

**Created**: 2026-05-20

**Status**: Draft

**Input**: User description: "Make speakloop ready for public GitHub release: discoverable, portable, and self-explanatory enough that someone cloning the repo on a fresh machine can install it, find the questions, run a session, and know what to do when something goes wrong — without ever messaging the maintainer."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clone, install, and finish a first session (Priority: P1)

A developer discovers speakloop from a referral, lands on the GitHub page, and wants
to try it. Reading only the repository's front-page documentation, they understand
what the tool is and who it is for, install it on a fresh Apple Silicon machine,
locate the question content inside the repo, and complete one practice session that
produces a saved report — all without contacting the maintainer.

**Why this priority**: This is the entire point of the release. If a first-time
visitor cannot get from "landing on the page" to "a finished session report" on
their own, every other improvement is moot. It is the minimum viable slice: front-page
documentation plus in-repo question content plus a license is, by itself, a coherent
public release.

**Independent Test**: On a machine that is not the maintainer's, with no prior
knowledge of the project, follow only the front-page documentation to install,
locate the questions in the repo, and run one session to a completed report. Success
is a saved report file without the tester having read any source code.

**Acceptance Scenarios**:

1. **Given** a freshly cloned repository, **When** a new user looks for the practice
   questions, **Then** they find them at a discoverable in-repo location and can read
   the schema and edit them without touching any home-directory path.
2. **Given** a new user who has only read the front-page documentation, **When** they
   follow the installation and quickstart steps, **Then** they reach a completed
   session report in under 15 minutes (excluding model download time).
3. **Given** a new user reading the front-page documentation, **When** they finish a
   session, **Then** they already know where the report was saved and what its parts
   mean, because the documentation showed an annotated example beforehand.
4. **Given** the repository root, **When** a user or downstream tool looks for license
   terms, **Then** a license file is present at the root matching the project's
   mandated license.

---

### User Story 2 - Recover from a rough edge without help (Priority: P2)

A new user's first session hits one of the known rough edges — a model download
fails, the language-model feedback silently degrades to fluency-only, a technical
term is misheard, a version conflict breaks voice activity detection, the microphone
is blocked on macOS, or the recording loop hangs at the final attempt. They open the
front-page documentation, find the matching symptom, read the cause, and apply the
stated workaround (or learn it is a known v1 limitation) — without messaging the
maintainer.

**Why this priority**: The tool already handles most of these gracefully in code, but
a user who hits one with no documented recourse abandons the tool. This converts
silent rough edges into self-service recoveries. It depends on US1 existing (the
documentation must exist first) but is independently valuable and testable.

**Independent Test**: For each documented failure mode, simulate or describe the
symptom and confirm the troubleshooting entry names the cause and gives either a
concrete local fix or an explicit "known v1 limitation" statement.

**Acceptance Scenarios**:

1. **Given** a user whose session degraded to fluency-only feedback, **When** they
   consult the troubleshooting documentation, **Then** they learn which report field
   records the cause and what each cause means.
2. **Given** a user whose model download failed mid-way, **When** they consult the
   troubleshooting documentation, **Then** they learn how to resume the download and
   how to proceed in a network-restricted environment.
3. **Given** a user whose recording loop hangs at the final attempt, **When** they
   consult the troubleshooting documentation, **Then** they find the stated interim
   workaround and an explicit note that the underlying bug is known and deferred.
4. **Given** each documented failure mode, **When** a reader scans its entry, **Then**
   the symptom is visually prominent, the cause is one line, and the fix is a single
   short paragraph — no prose walls.
5. **Given** the front-page documentation, **When** a reader looks before the
   troubleshooting section, **Then** they find an honest "known limitations" summary
   stating this is v1, that accented technical jargon can be misheard, that
   language-model feedback can fail and degrade to fluency-only, and that audio replay
   exists while full pronunciation feedback does not.

---

### User Story 3 - Portable on any machine, enforced automatically (Priority: P2)

A contributor (or the maintainer on a future change) must be confident the repository
contains no absolute path tied to any individual's machine, so that a fresh clone
never crashes or misbehaves with no explanation. An automated audit scans all tracked
content and fails if any machine-specific absolute path is present, so the guarantee
holds over time rather than depending on vigilance.

**Why this priority**: A single leaked absolute path can break a fresh clone in a way
that is invisible to the maintainer (whose machine matches the path). The audit both
removes today's leaks and prevents future drift. It is independently testable and
delivers value even without the documentation work.

**Independent Test**: Run the audit against the current tree and confirm zero leaks
across source, tests, docs, specs, content, and root configuration files. Introduce a
deliberate fake leak and confirm the audit fails; remove it and confirm it passes.

**Acceptance Scenarios**:

1. **Given** the current repository, **When** the path-portability audit runs, **Then**
   it reports zero machine-specific absolute-path leaks across all tracked content.
2. **Given** a future change that reintroduces a machine-specific absolute path,
   **When** the audit runs, **Then** it fails and identifies the offending file.
3. **Given** the audit, **When** it executes, **Then** it completes deterministically
   in under 2 seconds.

---

### User Story 4 - Bring your own question set (Priority: P3)

A returning user wants to practice with their own personal question set rather than
the questions shipped in the repo. Following documented instructions, they point the
tool at a personal question file outside the repo, and the tool uses it instead of the
in-repo default — without modifying tracked files.

**Why this priority**: Personalization is valuable but secondary; the default in-repo
questions already make a fresh clone usable. This preserves the prior behavior for
existing users and power users without blocking the core release.

**Independent Test**: With a personal question file present at the documented override
location, run a session and confirm the tool loads the personal questions; remove it
and confirm the tool falls back to the in-repo default.

**Acceptance Scenarios**:

1. **Given** a personal question file at the documented override location, **When** a
   session starts, **Then** the tool loads the personal questions in preference to the
   in-repo default.
2. **Given** no personal question file, **When** a session starts, **Then** the tool
   loads the in-repo default questions.
3. **Given** the override mechanism, **When** a user reads the front-page
   documentation, **Then** the override location and precedence are stated.

---

### Edge Cases

- What happens when neither the in-repo default question file nor a personal override
  file is present or readable? The tool must fail with a clear, actionable message
  rather than a crash or an empty session.
- What happens when the in-repo question file and a personal override file both exist?
  Precedence must be deterministic and documented (override wins).
- What happens when a tracked file legitimately must reference a path that resembles a
  home directory (e.g., documentation showing the override location as `~/...`)? The
  audit must distinguish a generic, portable reference from a machine-specific leak so
  it does not produce false positives that block legitimate documentation.
- What happens to existing automated tests that load questions from the prior location?
  They must continue to pass, or have an explicitly documented migration.
- What happens when the annotated example report in the documentation is read by a
  visitor? It must contain no real recording, no real name, and no maintainer personal
  data.

## Requirements *(mandatory)*

### Functional Requirements

**Question content relocation (US1, US4)**

- **FR-001**: The repository MUST ship the default practice questions at a discoverable
  in-repo location so a fresh clone has questions immediately, without the user reading
  source code to find them.
- **FR-002**: The question loader MUST read from the in-repo default location when no
  personal override is present.
- **FR-003**: The system MUST support a documented personal-override location outside
  the repository; when an override question file is present, it MUST take precedence
  over the in-repo default.
- **FR-004**: The existing question content MUST be migrated into the new in-repo
  location with no loss of questions or schema fidelity.
- **FR-005**: The question-loader public signature MUST remain compatible such that
  existing tests loading questions continue to pass without modification, or any
  required change MUST be explicitly documented as a migration.
- **FR-006**: When no question file can be found or read at either location, the system
  MUST present a clear, actionable message rather than crashing or starting an empty
  session.

**Path portability audit (US3)**

- **FR-007**: An automated audit MUST scan all tracked files — including source, tests,
  documentation, specs, content, and root configuration files — for machine-specific
  absolute-path leaks (e.g. `/Users/<name>/`, `/home/<name>/`, `C:\Users\<name>\`).
- **FR-008**: The audit MUST fail when any machine-specific absolute-path leak is
  present and MUST identify the offending file(s).
- **FR-009**: The audit MUST distinguish portable, generic references (e.g. a documented
  `~/...` override path) from machine-specific leaks, avoiding false positives that would
  block legitimate documentation.
- **FR-010**: All machine-specific absolute-path leaks present in the repository at the
  start of this work MUST be removed so the audit passes on the current tree.
- **FR-011**: The audit MUST be deterministic and complete in under 2 seconds.

**Front-page documentation / README (US1, US2)**

- **FR-012**: The repository MUST include a front-page README at the root, written in
  plain Markdown that renders on the hosting platform without extensions.
- **FR-013**: The README MUST open with the value proposition — who the tool is for and
  why they should care — before any architecture or technology description.
- **FR-014**: The README MUST state supported platforms and a project status indicator.
- **FR-015**: The README MUST give installation steps and an end-to-end quickstart that
  takes a new user from clone to a first completed session.
- **FR-016**: The README MUST include one short, annotated example of a session report
  showing the speech-recognition provenance block, at least one grammar pattern, and the
  top-priority line, so a new user sees what they will get before running.
- **FR-017**: The annotated example MUST use generic content only — no real recording,
  no real name, no maintainer personal data.
- **FR-018**: The README MUST state where reports are saved and where the questions live.
- **FR-019**: The README MUST link to the project constitution and the specs directory
  for contributors.
- **FR-020**: The README MUST be readable end-to-end in about 5 minutes by a developer
  who has never seen the project.

**Known limitations and troubleshooting (US2)**

- **FR-021**: The README MUST include a "known limitations" summary, placed before the
  troubleshooting section, that honestly states this is v1, that accented technical
  jargon can be misheard despite biasing, that language-model feedback can fail and
  degrade to fluency-only, and that audio replay exists while full pronunciation
  feedback does not.
- **FR-022**: The README MUST include a troubleshooting section. Each entry MUST present
  a prominent symptom, a one-line cause, and a single short-paragraph fix — scannable,
  not prose walls.
- **FR-023**: Troubleshooting MUST cover, at minimum: model download failures (resume and
  network-restricted/proxy notes); language-model feedback silently degraded to
  fluency-only (which report field records the cause and what each cause means);
  technical terms misheard by speech recognition (the current limitation and how the
  per-session biasing works, including how to add domain terms); voice-activity-detection
  version conflicts (why the dependency is pinned and how to recover if a newer version is
  installed); microphone permissions on macOS first run; and the recording loop hanging at
  the final attempt (the interim abort workaround and an explicit note that the bug is
  known and deferred).
- **FR-024**: Every documented failure mode MUST end with either a fix the user can apply
  locally or an explicit "known v1 limitation" statement.

**License (US1)**

- **FR-025**: The repository MUST include a license file at the root matching the license
  mandated by the project constitution.

**Internal documentation consistency (US1)**

- **FR-026**: Internal documentation that references the prior question location
  (including module guidance files and specs) MUST be updated to reference the new in-repo
  default location and the override mechanism.

**Constraints preservation (all stories)**

- **FR-027**: All changes MUST preserve the project's governing principles: offline-first
  operation, English-only user interface, report schema version unchanged, modular
  boundaries, and swappable engines.
- **FR-028**: No new third-party dependency may be introduced for any of these changes.

### Key Entities *(include if feature involves data)*

- **Question set**: The collection of practice questions and their schema. Now has a
  default in-repo location and an optional personal-override location, with the override
  taking precedence.
- **Front-page README**: The single document a first-time visitor reads. Contains pitch,
  platforms/status, install, quickstart, annotated report example, contributor links,
  known limitations, and troubleshooting.
- **Troubleshooting entry**: A unit of the troubleshooting section — symptom, cause, and
  fix (or known-limitation statement).
- **Path-portability audit**: An automated check that classifies tracked-file content as
  portable or machine-specific-leak and gates on the result.
- **License file**: Root-level statement of usage terms matching the mandated license.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-A**: A fresh clone on a machine other than the maintainer's, operated by someone
  following only the README, reaches a completed session report in under 15 minutes
  (excluding model download time).
- **SC-B**: The automated absolute-path audit reports zero leaks across source, tests,
  docs, specs, content, and root configuration files, and fails on any future leak.
- **SC-C**: A reader can answer all of the following from the README alone, without
  reading source code: what the tool does, how to install it, how to run a first session,
  where the questions live, where reports are saved, and where to look when something
  fails.
- **SC-D**: Every documented failure mode in the troubleshooting section is matched to
  either a locally applicable fix or an explicit "known v1 limitation" statement.
- **SC-E**: A license file exists at the repository root and matches the license the
  constitution mandates.
- **SC-F**: The questions file is editable in the repository without going through any
  home-directory path, and users with a personal question file can still use it via the
  documented override.
- **SC-G**: The path-portability audit completes deterministically in under 2 seconds.

## Assumptions

- The default in-repo question location is a new top-level `content/questions.yaml`
  directory at the repository root (distinct from the existing `src/speakloop/content/`
  package module), chosen for discoverability and to match the cwd-relative convention
  already used for `data/sessions/`; the exact filename is an implementation detail
  confirmable during planning.
- The personal-override location is the prior home-directory path, preserving behavior
  for existing users; the override is opt-in by presence of that file.
- "The license the constitution mandates" is MIT, per the constitution's
  Non-Negotiables.
- Supported platform is macOS Apple Silicon with Python 3.12, consistent with prior
  features; the README states this explicitly.
- The annotated report example in the README is hand-authored generic content, not a
  captured real session.
- The audit runs as part of the existing automated test suite (no new CI/CD setup is in
  scope); "fails CI" means the test fails wherever the suite is executed.
- Fixing the final-attempt recording-loop hang, ASR accuracy improvements, and any new
  features are explicitly out of scope and are only documented as limitations.
