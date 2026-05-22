# Feature Specification: Context Engineering Audit & Rewrite of the CLAUDE.md Layer

**Feature Branch**: `005-context-engineering-audit`

**Created**: 2026-05-21

**Status**: Draft

**Input**: User description: "Apply rigorous context engineering to speakloop so that any AI coding agent — Claude Code, future-Claude sessions, or another LLM — can contribute productively within minutes of opening the repo, without ad-hoc explanations from the maintainer. Treat the project's context layer (CLAUDE.md files at every scope, .claude/rules/, slash commands, and research docs) as a first-class deliverable governed by the same discipline as code: short, concrete, single-source-of-truth, and reviewed regularly."

<!--
SCOPE NOTE (human-only, stripped before injection): This feature treats the
repository's context layer (CLAUDE.md at every scope, .claude/rules/, the
research doc) as the deliverable. The "users" are AI coding agents and human
contributors. The authoritative source of truth is the CODE in src/speakloop/
and tests/ — not the specs, not the existing CLAUDE.md files, not the research
doc. Code wins on every disagreement; the constitution is the sole read-only
authority and wins only when a documentation rule conflicts with a principle.
Every design decision traces to a numbered claim in
doc/research_context_engineering.md Section 17 (the "claim ledger").
-->

## Clarifications

### Session 2026-05-21

- Q: How should the per-module anatomy handle top-level sections (global tech-stack, build/test/lint commands) that don't map to module scope? → A: Module-adapted order — keep the shared section order but omit sections with no module-scope meaning; always include the Principle IV six fields.
- Q: What mechanism produces the adversarial-review verdict for the top-level CLAUDE.md (FR-014/SC-C), given sub-agent design is out of scope? → A: A fresh review sub-agent (Explore/general-purpose) reads only the rewritten file plus the code and reports divergences by severity; the verdict is recorded in the audit artifacts.
- Q: What review cadence should the documented maintenance process state (FR-020/SC-E)? → A: Per-feature + per-PR — a context-layer review on each new `specs/NNN-*` feature, plus PR-coupling for any convention change (no calendar interval).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy launch-time map for any AI agent (Priority: P1)

A coding agent (Claude Code, a future Claude session, or another LLM tool) opens
the repository for the first time. It reads the top-level `CLAUDE.md` — the only
context file loaded automatically at launch — and within seconds knows what
speakloop is, what it is built with, how the modules depend on one another, which
build/test/lint commands to run, which traps to avoid, and what it must never do.
Every fact it reads is true of the actual code, so it does not need an ad-hoc
explanation from the maintainer to start contributing.

**Why this priority**: The top-level `CLAUDE.md` is the single file every session
pays for (loaded at launch, re-injected after `/compact`). A correct, code-true,
well-shaped top-level file is the highest-leverage deliverable and is independently
valuable even if nothing else in this feature ships. It is the MVP.

**Independent Test**: Rewrite only the top-level `CLAUDE.md` (plus the audit
inventory covering its claims) and run the adversarial review against the code —
the file delivers a complete, trustworthy onboarding map on its own.

**Acceptance Scenarios**:

1. **Given** a fresh agent reading only the top-level `CLAUDE.md`, **When** it
   looks for the project's purpose, tech stack, and module layout, **Then** all
   three are present in the canonical anatomy order, and every stated fact traces
   to a `file:line` location in the code.
2. **Given** the rewritten top-level `CLAUDE.md`, **When** a fresh review sub-agent
   (reading only the file plus the code, per the sprint-3 docs-audit pattern) checks
   each claim against the code, **Then** zero CRITICAL or MAJOR divergences are found
   and the verdict is recorded in the audit artifacts.
3. **Given** the build/test/lint commands listed in the file, **When** each is
   actually executed, **Then** each runs as documented, and no command that fails
   or does not exist remains documented (the `speakloop doctor` reference is
   resolved by running it).
4. **Given** the "known traps" section, **When** entries are counted and checked,
   **Then** there are at least 5 entries and each cites a commit hash, a
   session-report path, or a `specs/` reference.
5. **Given** the "how to maintain this context layer" section, **When** a
   contributor reads it, **Then** it states concrete rules (review cadence,
   correct-twice-then-record, PR-coupling, split-on-overflow), is readable and
   applicable in under 2 minutes, and contains no vague exhortation.
6. **Given** the finished file, **When** its length and language are measured,
   **Then** it is under 200 lines and entirely in English.

---

### User Story 2 - On-demand module guidance that loads only when needed (Priority: P2)

An agent works inside one module (say `asr/`). When it reads a file there, that
module's `CLAUDE.md` joins the context for that work — without bloating every other
session. Each module file follows the same predictable anatomy, names the file
boundaries and engine imports the module owns exclusively, and is verified against
the module's actual code, so the agent can modify one module without loading the
rest of the codebase (Constitution Principles IV, V, XI).

**Why this priority**: Per-module files are the just-in-time layer that keeps the
launch footprint small. They matter, but the top-level map (US1) delivers value
first; module files refine the per-module experience.

**Independent Test**: Rewrite the 13 module `CLAUDE.md` files to the shared
anatomy and verify each engine import lives in exactly one wrapper — testable
module-by-module against the code without touching the top-level file.

**Acceptance Scenarios**:

1. **Given** any of the 13 module `CLAUDE.md` files, **When** its structure is
   inspected, **Then** it follows the shared anatomy in the same relative order as
   every other module file — omitting sections with no module-scope meaning (global
   tech-stack, global commands) rather than padding them.
2. **Given** a module `CLAUDE.md`, **When** it is checked against Constitution
   Principle IV, **Then** it covers purpose, public interface, dependencies,
   consumers, file map, and common modification patterns.
3. **Given** a module that owns an engine import (e.g., `asr/`, `llm/`, `tts/`),
   **When** the import scan runs, **Then** the engine package (e.g., `mlx_whisper`,
   `mlx_lm`, `kokoro`) is imported in exactly one wrapper file, and the module's
   `CLAUDE.md` names that boundary (Principle V).
4. **Given** each module `CLAUDE.md`, **When** its length is measured, **Then** it
   is under 100 lines.
5. **Given** any module `CLAUDE.md` rewrite, **When** its provenance is checked,
   **Then** the module's `__init__.py` and primary public entry points were read
   first and recorded in the module-read list.

---

### User Story 3 - Scoped rules and the research reference, within a bounded launch footprint (Priority: P3)

The maintainer and future agents want topic-scoped rules where they genuinely
reduce per-session context, plus the context-engineering research doc available in
the repo as the "why" behind the rules — all without growing the tokens loaded at
launch. Scoped rule files are added only where investigation shows they earn their
place; the research doc is sanitized of any personal path so the project's
path-portability audit stays green.

**Why this priority**: These are refinements layered on top of a healthy
CLAUDE.md set. Adding rules speculatively would violate the discipline this
feature is enforcing, so this work is deliberately last and deliberately optional.

**Independent Test**: Decide and (if justified) add `.claude/rules/*.md` with
`paths` frontmatter, commit the sanitized research doc, and confirm the
path-portability audit passes and the launch footprint stays within budget.

**Acceptance Scenarios**:

1. **Given** an investigation of real session friction, **When** deciding whether
   to add `.claude/rules/*.md`, **Then** a rule file is added only where justified;
   each added file carries `paths` frontmatter and an HTML-comment justification
   (why module-scope rule vs. in the relevant `CLAUDE.md` vs. skipped); and if none
   is justified, none is added and that decision is recorded.
2. **Given** `doc/research_context_engineering.md` committed to the repo, **When**
   the path-portability audit runs, **Then** it passes — no maintainer personal
   path remains (the line-3 `/Users/...` path is removed) and content is in English.
3. **Given** the set of files loaded at launch (top-level `CLAUDE.md` plus any
   unscoped rule files plus any imports), **When** the footprint is measured,
   **Then** it is within the budget set in planning, and nested module `CLAUDE.md`
   files and `paths`-scoped rules contribute zero launch tokens.

---

### Edge Cases

- **A test asserts on CLAUDE.md content.** `tests/integration/test_help_without_models.py`
  references `CLAUDE.md`. The audit must determine whether it asserts on the file's
  *content* (which would couple tests to docs and could break under a rewrite). If
  so, it is flagged as a separate finding (SC-H); a test is never weakened to
  accommodate a documentation rewrite.
- **A referenced command may not exist.** `speakloop doctor` is named in several
  docs but is unconfirmed. It is resolved by actually running it; if it fails or is
  missing, it is removed from documentation, not assumed.
- **A referenced verification test may not exist.** An "engine-isolation test" is
  assumed by the brief, but only `test_path_portability_audit.py` is confirmed.
  Engine isolation is verified by an import scan as the authoritative method; a
  missing dedicated test is flagged as a separate finding, not created here.
- **A trap candidate has no evidence.** A candidate from the historical list that
  cannot be traced to a commit, a session report, or a `specs/` reference is
  dropped, not added (SC-D).
- **A module file is too thin for Principle IV.** Some module files are 9–11 lines
  today and cannot cover all six required fields; they are expanded to cover them
  while staying under 100 lines.
- **A pointer is broken.** A cross-reference to a renamed or missing file is flagged
  and fixed in the live doc.
- **A documentation rule conflicts with a constitution principle.** The principle
  wins; the rule is removed or rewritten (e.g., a rule must not contradict
  English-only output or engine isolation).
- **A finding requires a code change.** If making a claim or command true would
  require touching code, it is flagged separately and deferred unless trivial; code
  is not changed silently to fit the docs.
- **The research doc is Android-flavored.** Its examples reference an Android/Gradle
  project ("WalletFlow"); they are reference illustrations and are not rewritten to
  speakloop. Only path sanitation and English are required of it; speakloop-specific
  rules live in `CLAUDE.md`, and design decisions trace to its claim ledger.

## Requirements *(mandatory)*

### Functional Requirements

#### Audit & evidence (foundational; underpins all stories)

- **FR-001**: The system MUST produce a divergence inventory in which each row
  records a claim (with `file:line` in the relevant `CLAUDE.md`), the ground truth
  from code (with `file:line` in `src/speakloop/`, `tests/`, or `pyproject.toml`),
  a severity, and a recommended action. Code is the source of truth; specs, existing
  `CLAUDE.md` files, and the research doc are not.
- **FR-002**: The system MUST produce a module-read list covering every directory
  under `src/speakloop/` (the 13 modules: `asr`, `audio`, `cli`, `config`,
  `content`, `debrief`, `feedback`, `installer`, `llm`, `metrics`, `sessions`,
  `trends`, `tts`), each with a one-line summary of what was verified by reading at
  least the module's `__init__.py` and primary public entry points. No module
  `CLAUDE.md` is rewritten for a module not read in full.
- **FR-003**: The system MUST produce a command matrix listing every command
  claimed in any `CLAUDE.md`, each marked verified / failed / missing by actually
  running it. Commands that fail or do not exist MUST be removed from documentation;
  commands that exist but are undocumented MUST be added. The existence of
  `speakloop doctor` MUST be resolved by running it.
- **FR-004**: The system MUST produce a known-traps candidate list where each
  retained entry cites evidence — a commit hash, a session-report path, or a
  `specs/` post-ship-fix reference. Candidates without evidence MUST be dropped.
- **FR-005**: The system MUST produce a cross-reference link-check: every pointer
  from a `CLAUDE.md` to another file (other `CLAUDE.md` files, `specs/`, `doc/`, the
  constitution) is checked against the actual target, and broken links are flagged
  and fixed in live docs.
- **FR-006**: The system MUST verify Constitution Principle V engine isolation by
  scanning imports (ripgrep or AST), confirming each **directly-imported** engine
  package (`mlx_whisper`, `silero_vad`, `parakeet_mlx`, `mlx_lm`, `kokoro_mlx`) is
  imported in exactly one wrapper file, and recording the owning file. `onnxruntime`
  is **transitive via `silero_vad`** and has no direct import in `src/speakloop/`; the
  existing `asr/CLAUDE.md` claim that `vad.py` imports `onnxruntime` is divergence D-1
  and is corrected during the asr module rewrite. The existing path-portability test
  assertions are authoritative; a missing dedicated engine-isolation test is flagged
  as a separate finding.
- **FR-007**: The module dependency graph used in the top-level layout section MUST
  be derived from an actual import scan, not from prose in existing `CLAUDE.md`
  files; the resulting graph in the top-level `CLAUDE.md` is authoritative.

#### Top-level CLAUDE.md (User Story 1)

- **FR-010**: The top-level `CLAUDE.md` MUST be rewritten to the canonical 9-section
  anatomy in this fixed order: (a) project overview in 2–3 sentences; (b) tech stack as
  a fixed list derived from `pyproject.toml` and verified against actual imports
  (including Python 3.12, `uv`, `mlx-whisper`, `mlx-lm`, `kokoro-mlx`, `silero-vad`,
  `onnxruntime` (transitive), `parakeet-mlx`, and the `torchaudio<2.9` cap); (c) module
  layout with dependency rules from the import scan; (d) verified build/test/lint
  commands; (e) conventions cross-verified against code and the constitution;
  (f) maintenance ("how to maintain this context layer", per FR-020); (g) known traps
  with evidence citations; (h) never-do list with code-pattern citations where
  applicable; (i) pointers to per-module `CLAUDE.md`, `specs/`, `doc/research_*.md`,
  and the constitution.
- **FR-011**: The known-traps section of the top-level `CLAUDE.md` MUST contain at
  least 5 entries, each evidence-traced per FR-004.
- **FR-012**: Every command documented in any `CLAUDE.md` MUST be verified to work
  during this feature, and that verification recorded (per FR-003).
- **FR-013**: The top-level `CLAUDE.md` MUST be under 200 lines.
- **FR-014**: The rewritten top-level `CLAUDE.md` MUST pass an adversarial review
  against the code with zero CRITICAL or MAJOR divergences; every claim MUST trace
  to a `file:line` location in code. The review MUST be conducted by a fresh review
  sub-agent (e.g., the Explore or general-purpose agent) that reads only the
  rewritten file plus the code — independent of the author — and reports divergences
  by severity; its verdict MUST be recorded in the audit artifacts under the feature
  directory. (This uses an agent for review only; no persistent sub-agent is a
  shipped deliverable — sub-agent design remains out of scope.)
- **FR-015**: The top-level `CLAUDE.md` MUST continue to render correctly in the
  existing `/speckit-*` workflow (the `.specify/` machinery reads it).

#### Maintenance discipline (User Story 1)

- **FR-020**: The top-level `CLAUDE.md` MUST include a "how to maintain this context
  layer" section stating concrete rules: review on a stated cadence; if the agent is
  corrected on the same thing twice, record it in the relevant `CLAUDE.md`; every PR
  that changes a convention updates the relevant `CLAUDE.md` in the same commit; when
  a file exceeds its line limit, split it via `paths`-scoped rules or a nested
  `CLAUDE.md`. The stated review cadence MUST be feature-driven, not calendar-driven:
  every new `specs/NNN-*` feature triggers a context-layer review, in addition to the
  per-PR convention-change coupling above (no fixed calendar interval). The section
  MUST itself follow the anatomy discipline (concrete rules, no vague exhortation)
  and be applicable in under 2 minutes.

#### Per-module CLAUDE.md (User Story 2)

- **FR-030**: All 13 module `CLAUDE.md` files MUST be rewritten to the shared anatomy
  at module scope, preserving the canonical section *order*. Sections with no
  module-scope meaning (the global tech-stack list; global build/test/lint commands)
  MUST be omitted rather than padded with "N/A"; the Principle IV six fields (FR-031)
  MUST always be present. Among the sections that do apply, every module file MUST
  place them in the same relative order so structure stays predictable.
- **FR-031**: Each module `CLAUDE.md` MUST cover the fields mandated by Constitution
  Principle IV — purpose, public interface, dependencies, consumers, file map, and
  common modification patterns — i.e., the shared anatomy MUST superset Principle IV.
- **FR-032**: Each module `CLAUDE.md` MUST state the engine-import boundary the
  module owns (per Principle V), verified by the import scan (FR-006).
- **FR-033**: Each module `CLAUDE.md` MUST be under 100 lines.
- **FR-034**: No module `CLAUDE.md` MUST be written for a module not read in full
  per FR-002.

#### Scoped rules & research doc (User Story 3)

- **FR-040**: `.claude/rules/*.md` files MUST be added only where investigation
  justifies them. Each added rule file MUST carry `paths` frontmatter scoping it to
  file globs and an HTML-comment justification explaining why it earns module-scope
  placement versus living in the relevant `CLAUDE.md` versus being skipped. If no
  rule file is justified, none is added and the decision is recorded.
- **FR-041**: `doc/research_context_engineering.md` MUST be present in the repo with
  no maintainer personal path (the existing line-3 `/Users/<name>/...` path
  MUST be removed) and with content in English.
- **FR-042**: The path-portability audit (`tests/integration/test_path_portability_audit.py`)
  MUST stay green with the research doc and all changes committed.
- **FR-043**: The launch-time context footprint (top-level `CLAUDE.md` + any
  unscoped rule files + any imports) MUST stay within a budget quantified during
  planning; nested module `CLAUDE.md` files and `paths`-scoped rules MUST NOT load at
  launch.

#### Guardrails & non-regression (all stories)

- **FR-050**: All context-layer content MUST be in English (Constitution Principle I).
- **FR-051**: `.specify/memory/constitution.md` MUST NOT be modified; it is a
  read-only authoritative input.
- **FR-052**: Historical specs (`specs/001`–`specs/004`) MUST NOT be rewritten; only
  cross-references in live docs are updated.
- **FR-053**: Changes in this feature MUST NOT touch application code. If a finding
  requires a code change, it MUST be flagged separately and deferred unless trivial.
  The full pytest suite MUST stay green throughout.
- **FR-054**: If any test asserts on `CLAUDE.md` *content*, it MUST be flagged as a
  separate finding; no test is weakened to accommodate a documentation rewrite.
- **FR-055**: HTML comments (stripped before injection, so zero context cost) MUST
  carry the human-only "why" notes and rule-file justifications; pointers are
  preferred over `@`-imports, and import depth MUST stay within 5 hops.
- **FR-056**: Every non-obvious design decision in the rewritten context layer MUST
  trace to a numbered claim in the research doc's claim ledger (Section 17).

### Key Entities

- **Context file**: a `CLAUDE.md` at a given scope (repo root or a module). Key
  attributes: scope, ordered anatomy sections present, line count, load timing
  (launch vs. on-demand), language.
- **Divergence record**: a claim reference (`file:line` in a `CLAUDE.md`), a
  ground-truth reference (`file:line` in code), a severity (CRITICAL / MAJOR /
  MINOR / INFO, per the sprint-3 scale), and a recommended action.
- **Known-trap entry**: a description plus an evidence reference (commit hash,
  session-report path, or `specs/` reference).
- **Command record**: a command string and a status (verified / failed / missing).
- **Cross-reference**: a source file (and anchor), a target path, and whether it
  resolves.
- **Scoped rule file**: a `.claude/rules/*.md` with a `paths` glob scope and an
  HTML-comment justification.
- **Claim-ledger reference**: a mapping from a research-doc claim number (Section
  17) to the design decision it justifies.

## Success Criteria *(mandatory)*

<!-- IDs preserved from the brief (SC-A..SC-I) for traceability into plan/tasks,
plus SC-J..SC-L for measurable outcomes surfaced during reconnaissance. -->

### Measurable Outcomes

- **SC-A**: Every `CLAUDE.md` in the repository is under its ceiling — top-level
  under 200 lines, each per-module file under 100 lines.
- **SC-B**: Every `CLAUDE.md` follows the shared 9-slot anatomy spine in the same
  relative order (overview, scope/stack, layout/boundaries, commands, conventions,
  maintenance, traps, never-do, pointers). Module files omit slots that have no
  module-scope meaning (global tech-stack, global build/test/lint commands,
  maintenance) rather than padding them; for the slots that do appear, a reader finds
  them in the same relative place across modules, and the Principle IV six fields are
  always present.
- **SC-C**: An adversarial review of the rewritten top-level `CLAUDE.md` against the
  code — conducted by a fresh review sub-agent reading only the file plus the code,
  with its verdict recorded in the audit artifacts — produces zero CRITICAL or MAJOR
  divergences; claims trace to `file:line` in code.
- **SC-D**: The top-level known-traps section contains at least 5 entries, each
  traceable to a real past correction across sprints 1–4 with a commit hash,
  session-report reference, or `specs/` post-ship-fix reference.
- **SC-E**: The maintenance process is documented, follows the anatomy (concrete
  rules, not vague exhortation), states a feature-driven review cadence (per new
  `specs/NNN-*` feature plus per-PR convention-change coupling, no calendar interval),
  and a contributor can read and apply it in under 2 minutes.
- **SC-F**: `doc/research_context_engineering.md` is in the repo with no maintainer
  personal-path leakage, and the path-portability audit still passes.
- **SC-G**: Any added `.claude/rules/*.md` file has a clear `paths` frontmatter scope
  and an HTML-comment justification for why it earns module-scope placement versus
  the relevant `CLAUDE.md` versus being skipped.
- **SC-H**: The full pytest suite stays green throughout; no existing test breaks
  because of `CLAUDE.md` changes, and any test that asserts on `CLAUDE.md` content is
  flagged as a separate finding.
- **SC-I**: Every command documented in any `CLAUDE.md` has been verified by actually
  running it during this feature and recorded as verified.
- **SC-J**: Zero broken cross-references remain in live `CLAUDE.md` files — every
  pointer resolves to an existing target.
- **SC-K**: The launch-time context footprint stays within the planning-defined
  budget; nested module files and `paths`-scoped rules contribute zero launch tokens.
- **SC-L**: Every directly-imported engine package (`mlx_whisper`, `silero_vad`,
  `parakeet_mlx`, `mlx_lm`, `kokoro_mlx`) resolves to exactly one wrapper file, recorded
  in the audit (Constitution Principle V). `onnxruntime` is transitive via `silero_vad`
  and has no direct import; it is recorded as transitive (divergence D-1), not as an
  owned wrapper.

## Assumptions

- **Code-wins precedence.** When specs, existing `CLAUDE.md` files, or the research
  doc disagree with the code, the code is ground truth. The constitution is the sole
  exception: it is read-only authoritative governance, and when a documentation rule
  conflicts with a principle, the principle wins.
- **Files already fit the ceilings.** Reconnaissance shows the top-level file is 69
  lines and module files are 9–46 lines, all already under their limits. The work is
  anatomy, signal, and accuracy rationalization — not primarily trimming. Several
  thin module files (9–11 lines) cannot currently cover Principle IV's six fields and
  will be expanded (still under 100 lines).
- **Anatomy supersets Principle IV.** The shared per-module anatomy is arranged so
  that purpose, public interface, dependencies, consumers, file map, and common
  modification patterns are all present, satisfying Principle IV without a separate
  shape.
- **`speakloop doctor` is unconfirmed.** Its existence is resolved by running it
  during the audit; the spec does not assume it exists.
- **A dedicated engine-isolation test may not exist.** Engine isolation is verified
  by import scan as the authoritative method; a missing test is a separate finding,
  not created here (no new tests are in scope beyond command-existence checks).
- **Scoped rules are a planning decision.** Whether any `.claude/rules/*.md` is
  warranted is decided during planning from observed friction; the spec permits zero
  rule files if none earns its place.
- **The launch-footprint budget is set in planning.** The spec requires the footprint
  to be bounded; the concrete budget value is quantified during planning.
- **Audit artifacts persist under the feature directory.** The divergence inventory,
  module-read list, command matrix, trap-evidence list, and cross-reference check are
  saved under `specs/005-context-engineering-audit/`, following the sprint-3
  docs-audit and sprint-4 path-audit pattern.
- **The research doc is repurposed reference material.** Its Android/Gradle examples
  are illustrative and are not rewritten to speakloop; only path sanitation and
  English are required. Its claim ledger (Section 17) is platform-agnostic and is the
  authoritative trace target.
- **Python is pinned to 3.12.** `pyproject.toml` sets `requires-python = ">=3.12,<3.13"`;
  the tech-stack section states what the code requires.
- **Maintenance is a documented process, not an automated gate.** Per the "no new
  tests" boundary, line limits and link integrity are upheld by the documented
  discipline and review, not by a new enforcement test.

## Dependencies

- The code in `src/speakloop/` and `tests/` as the authoritative ground truth.
- A runnable environment to execute and verify build/test/lint commands (`uv`,
  `pytest`, `ruff`, and the `speakloop` CLI).
- Git history (`git log`) for trap evidence across sprints 1–4.
- The sprint-4 path-portability audit (`tests/integration/test_path_portability_audit.py`)
  as the gate for personal-path leakage.
- The `.specify/*` workflow, which reads the top-level `CLAUDE.md` and must continue
  to render it correctly.
- `doc/research_context_engineering.md` (already copied into the repo) as the
  authoritative reference and claim ledger.

## Out of Scope

- Editing `.specify/memory/constitution.md` (read-only authoritative input).
- New code, new features, or new tests, except those needed to verify a command's
  existence (none anticipated).
- Auto-memory tuning, MCP server integration, and prompt-caching configuration
  (runtime concerns; separate features).
- Sub-agent design (deferred to a later sprint).
- Rewriting historical specs (`specs/001`–`specs/004` remain historical records).
- Any GUI, web interface, or external documentation site (terminal-first project;
  README + `CLAUDE.md` are the surface).
- The `README.md` (already rewritten in sprint 4).
