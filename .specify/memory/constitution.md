<!--
SYNC IMPACT REPORT
==================
Version change: (template / unfilled) → 1.0.0
Bump rationale: Initial ratification. The prior file was an unfilled template with no
governing principles; this commit establishes the first canonical constitution for
speakloop, so a 1.0.0 MAJOR baseline is appropriate.

Modified principles: N/A (initial ratification — all 12 principles are new)
  I.    English-Only User Interface
  II.   Offline-First
  III.  Privacy by Design
  IV.   Modular by Design (NON-NEGOTIABLE)
  V.    Swappable Engines
  VI.   Resumable Model Downloads
  VII.  Apple Silicon Primary Target
  VIII. Easy Install for Everyone
  IX.   Obsidian-Compatible Feedback Reports
  X.    Research is Part of the Repo
  XI.   AI-Collaborator Friendly
  XII.  Iterative Delivery

Added sections:
  - Core Principles (I–XII)
  - Non-Negotiable Constraints
  - Development Guidelines
  - User Context
  - Governance

Removed sections: N/A (initial ratification)

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — "Constitution Check" gate is generic
     ("[Gates determined based on constitution file]") and resolves against this
     document; no edit required.
  ✅ .specify/templates/spec-template.md — No principle-name references; compatible.
  ✅ .specify/templates/tasks-template.md — Task categories (Setup, Foundational,
     User Story, Polish) are compatible with Principle XII (Iterative Delivery).
  ✅ .specify/templates/checklist-template.md — Generic; compatible.
  ⚠ Top-level CLAUDE.md — Does not yet exist. Principle IV requires one describing
     overall architecture and pointing to module-level CLAUDE.md files. Create when
     the first module lands (tracked as follow-up, not a blocker for ratification).
  ⚠ doc/ research documents — Principle X names four required files
     (research_tts.md, research_asr.md, research_llm.md, research_methodology.md).
     The doc/ directory exists but contents are not verified by this command;
     ensure all four are present before tagging v1.0.

Follow-up TODOs:
  - Author top-level CLAUDE.md once `src/` exists (Principle IV, XI).
  - Verify all four research_*.md files exist under doc/ (Principle X).
  - No deferred placeholders in this document — all bracketed tokens have been
    resolved with concrete values.
-->

# speakloop Constitution

speakloop is a fully local, offline English speaking-practice tool for non-native
software engineers preparing for international interviews. It runs three local AI
models (TTS, ASR, LLM) on Apple Silicon to deliver a structured practice loop:
listen to a natively-spoken interview question plus an ideal answer, attempt your
own answer under time pressure using the 4/3/2 method, and receive an
evidence-based feedback report focused on grammar patterns and fluency metrics.

This constitution governs every decision in the repository. When a code change,
design choice, or dependency conflicts with a principle below, the principle wins
until the constitution is amended through the process in **Governance**.

## Core Principles

### I. English-Only User Interface

Every byte of user-facing output — CLI prompts, reports, help text, error
messages, log lines — MUST be in English. v1 ships no localization layer, no
gettext/po files, and no per-locale formatting.

**Rationale:** The target user is preparing for English-language interviews;
exposing them to anything but native English in the tool itself would undermine
the practice loop and inflate scope.

### II. Offline-First

After the initial model download, the system MUST make zero network calls. No
telemetry, no analytics, no phone-home, no auto-updates, no remote feature flags.
User data never leaves the device.

**Rationale:** Privacy, bandwidth respect, and trust. A practice tool that
silently exfiltrates audio of the user speaking is unacceptable; offline-by-
default makes that class of leak architecturally impossible.

### III. Privacy by Design

Audio recordings, transcripts, and feedback reports MUST stay on the user's
machine. The user owns and controls all data produced. No file is uploaded,
mirrored, or sent to a third party by any code path in this repository.

**Rationale:** Recorded voice and self-assessment data are intimate. The default
state for such data is "the user's only" — anything else requires explicit, per-
session, opt-in consent that v1 does not solicit.

### IV. Modular by Design (NON-NEGOTIABLE)

Each functional concern MUST be its own module with a single responsibility.
Modules communicate only through explicit, documented interfaces. Every module
MUST ship with its own CLAUDE.md describing: purpose, public interface,
dependencies, consumers, file map, and common modification patterns. A module
without a CLAUDE.md is incomplete and MUST NOT be merged.

**Rationale:** Modularity is what makes future AI-assisted development cheap. The
per-module CLAUDE.md is the contract that lets an agent modify one module without
loading the rest of the codebase. This principle is the load-bearing wall of the
project.

### V. Swappable Engines

TTS, ASR, and LLM engines MUST sit behind stable interfaces. Replacing any one
engine — for example switching TTS from Kokoro to Piper, or LLM from Qwen to
Llama — MUST require changes in exactly one module file. No engine-specific
imports, configuration, or logic may leak across module boundaries.

**Rationale:** The local-AI landscape moves fast. Locking the project to a
specific TTS/ASR/LLM vendor would make the codebase obsolete within a year;
strict interface boundaries let us follow the frontier without rewrites.

### VI. Resumable Model Downloads

Model downloads MUST survive network interruptions. Partial downloads persist
across runs. The installer MUST NOT re-download what is already complete on
disk. The implementation SHOULD use HuggingFace Hub's resumable download
primitives (or an equivalent that provides byte-range resume).

**Rationale:** The target user has unreliable internet. A multi-gigabyte download
that restarts from zero on every dropped connection is a hard blocker to
adoption.

### VII. Apple Silicon Primary Target

M-series Macs are the design target for v1. Performance budgets, model choices,
and integration tests MUST assume Apple Silicon. Intel Mac, Linux, and Windows
are best-effort and explicitly out of scope until v2; bugs filed against them in
v1 are documented as such and not gating.

**Rationale:** Local TTS/ASR/LLM performance on consumer hardware is only
acceptable today on Apple Silicon (MLX, Metal, unified memory). Designing for the
union of all platforms in v1 would dilute every engine choice.

### VIII. Easy Install for Everyone

Any developer MUST be able to `git clone` and `uv run speakloop` and reach a
working setup. The first run MUST guide the user through model downloads with
informed consent and clear size disclosure (per-model size in MB/GB, total
disk footprint). `speakloop --help` MUST work without requiring models or full
installation.

**Rationale:** Friction at install is where open-source local-AI tools die. If
`--help` requires a 4 GB download, the tool effectively does not exist.

### IX. Obsidian-Compatible Feedback Reports

Session reports MUST be written as Markdown files with YAML frontmatter in
`data/sessions/`. They MUST render and link cleanly when the folder is opened as
an Obsidian vault. Filename convention: `YYYY-MM-DD-qXX.md`. Frontmatter follows
a stable schema (see **Development Guidelines**).

**Rationale:** Practice value compounds when the user can review past sessions.
Obsidian is the lingua franca of personal Markdown knowledge bases; meeting its
conventions costs nothing and unlocks linking, tagging, and querying for free.

### X. Research is Part of the Repo

The research documents that informed system design MUST live in `doc/` at the
project root and MUST be versioned with the code. Specifically:

- `doc/research_tts.md` — TTS engine selection research
- `doc/research_asr.md` — ASR engine selection research
- `doc/research_llm.md` — LLM selection research
- `doc/research_methodology.md` — speaking-practice pedagogy (shadowing, 4/3/2
  task repetition, error-tagged feedback, Persian-L1 error patterns)

These documents are the authoritative reference for any future engine or
methodology change. Changing an engine without updating the corresponding
research_*.md is a constitution violation.

**Rationale:** The "why we picked this model" question recurs every quarter. If
the answer lives only in a Notion doc or a chat log, future maintainers
re-litigate solved decisions. In-repo research keeps the rationale next to the
code it justifies.

### XI. AI-Collaborator Friendly

The project structure exists specifically so an AI agent (Claude Code, Cursor,
etc.) can modify one module without reading the rest of the codebase. Module
boundaries, naming conventions, and per-module CLAUDE.md files are the primary
mechanism. Any change that meaningfully widens the context an agent must load to
work on a module is a regression and MUST be justified.

**Rationale:** This project is built by a solo developer collaborating with AI
agents. Optimizing for that workflow — small loadable units of context, clear
seams, no cross-module surprises — is a force multiplier, not a luxury.

### XII. Iterative Delivery

The system MUST be designed so the MVP — TTS-only listening practice — is usable
and valuable before ASR and LLM integration. Later phases add capability without
breaking earlier ones. Users MUST be able to use the partial system in production
while later phases are still being built.

**Rationale:** Three-model systems that ship only when all three work tend not to
ship. A working TTS-only loop is real, useful, and motivating; ASR and LLM are
strict supersets that bolt on without rework.

## Non-Negotiable Constraints

The following constraints are part of the constitution. Changing any of them
requires the amendment process in **Governance**.

- **Language**: Python 3.11+ (3.12 recommended).
- **Package manager**: `uv`. No `pip install`-driven workflows in docs or
  scripts.
- **Model storage**: Under `~/.speakloop/models/` (or the XDG-compliant equivalent on
  systems where XDG is configured).
- **User configuration**: YAML. No TOML, JSON, or `.env` for user-facing config.
- **UI surface**: CLI only in v1, rendered with `rich`. No GUI framework
  (Tkinter, Qt, Electron, web UI) ships in v1.
- **External services**: None beyond the initial model download from HuggingFace.
  No analytics SDKs, no error-reporting SaaS, no remote config.
- **License**: MIT.
- **Repository visibility**: Public on GitHub.

## Development Guidelines

The following are the working rules every contributor (human or AI) follows.
They are derived from the principles above and have the same authority.

- **Single responsibility per module.** If you need to explain a module's job
  with "and", split it. (Principle IV)
- **Interfaces before implementations.** Module signatures MUST be agreed before
  the module body is coded. (Principles IV, V)
- **Engine tests use cached fixtures.** Tests for TTS/ASR/LLM modules use small
  cached WAV/text fixtures committed to the repo. Live model calls in tests are
  forbidden. (Principles II, V)
- **Every module ships with its own CLAUDE.md.** A module without one is
  incomplete and MUST NOT be merged. (Principle IV)
- **Top-level CLAUDE.md is the map.** The repository root CLAUDE.md describes
  overall architecture and links to every module-level CLAUDE.md. (Principle XI)
- **Conventional Commits.** Commit messages follow the Conventional Commits
  specification (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, etc.).
- **Stable report schema.** Session-report YAML frontmatter follows a stable
  schema so future analytics scripts can rely on it without parser changes. The
  schema is versioned; breaking changes require a `schema_version` bump and a
  migration note. (Principle IX)
- **Explicit over clever; standard library over dependencies; boring over
  novel.** When two approaches solve the same problem, prefer the one a stranger
  can read in five minutes.

## User Context

The primary user is a non-native English speaker (Persian L1 in the original
case, but the system MUST work for any L1) preparing for senior-level technical
interviews at international companies. They are a skilled software engineer
comfortable with terminals, Python environments, and reading source code. They
have unreliable internet (hence Principle VI) and want a tool that respects
their time, their privacy, and their bandwidth.

Design decisions SHOULD be evaluated against this user. Friction acceptable for
a casual consumer (cloud signup, default telemetry, opaque downloads) is
unacceptable here; friction acceptable for an enterprise SRE (config files,
CLI-only, reading the source to debug) is welcome.

## Governance

**Authority.** This constitution supersedes all other practices, conventions,
and preferences in the repository. When a tool, dependency, or workflow conflicts
with a principle, the principle wins until the constitution is amended.

**Amendment procedure.** Any change to this document requires:

1. A pull request that edits `.specify/memory/constitution.md` and updates the
   version line and the Sync Impact Report at the top of the file.
2. A written justification in the PR description that names the principle(s)
   touched and the motivation.
3. Propagation: the PR MUST also update any dependent artifact whose semantics
   change — plan/spec/tasks templates, top-level CLAUDE.md, module-level
   CLAUDE.md files, README sections that quote principles. Stale references to
   removed or renamed principles MUST NOT remain after merge.
4. Approval by the project maintainer (currently the sole owner; expands to a
   majority of named maintainers if/when the project gains them).

**Versioning policy (semantic).**

- **MAJOR**: backward-incompatible removal or redefinition of a principle, or
  removal of a non-negotiable constraint.
- **MINOR**: a new principle or section is added, or existing guidance is
  materially expanded.
- **PATCH**: clarifications, wording fixes, typos, non-semantic refinements.

**Compliance review.** Every PR that touches application code MUST be reviewed
against this constitution. The plan, spec, and tasks workflows include an
explicit "Constitution Check" gate that resolves against this document. A
violation discovered post-merge is tracked as a bug, not absolved by precedent.

**Runtime guidance.** Day-to-day development guidance for AI agents and humans
lives in the top-level `CLAUDE.md` (when present) and in each module's
`CLAUDE.md`. Those files MUST defer to this constitution on any conflict.

**Version**: 1.0.0 | **Ratified**: 2026-05-18 | **Last Amended**: 2026-05-18
