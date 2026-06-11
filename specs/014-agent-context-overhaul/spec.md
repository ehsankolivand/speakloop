# Feature Specification: Agent Context Overhaul

**Feature Branch**: `014-agent-context-overhaul`

**Created**: 2026-06-11

**Status**: Draft

**Input**: User description: "Overhaul SpeakLoop's agent-facing project context so it is accurate to the current code and engineered per doc/research_context_engineering.md. Three sprints (010 interview-loop, 011 claude-code engine, 012 session speed/UX) changed the codebase substantially, but the context files (root CLAUDE.md, nested module CLAUDE.md files, .claude assets) were not maintained; agents working on the repo now risk context poisoning and confusion from stale or missing claims. This is a documentation-and-context feature: zero production code changes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate, lean root CLAUDE.md (Priority: P1)

A coding agent (or new human contributor) opens the repository for the first time and reads only the root CLAUDE.md. From that file alone they know what the project is, the fixed tech stack, which module may depend on which, the exact commands to build/test/run, the project's hard conventions, the traps that have actually bitten past contributors, what they must never do, and where deeper documentation lives — and every one of those statements is true of the code as it exists today.

**Why this priority**: The root CLAUDE.md is injected into every session automatically. A stale claim there poisons every future session; an accurate lean file is the single highest-leverage context artifact in the repository.

**Independent Test**: Give a fresh agent only the rewritten root CLAUDE.md plus a representative task and verify it routes to the correct files and rules. Independently audit every sentence in the file against the current code with file:line evidence.

**Acceptance Scenarios**:

1. **Given** the rewritten root CLAUDE.md, **When** every claim in it is checked against the current code, **Then** 100% of claims are verifiable with file:line evidence and zero stale claims remain.
2. **Given** the rewritten root CLAUDE.md, **When** its line count is measured, **Then** it is ≤200 lines.
3. **Given** the rewritten root CLAUDE.md, **When** its sections are listed, **Then** it contains: a 2–3 sentence overview; tech stack as a fixed list; module layout with dependency rules; exact build/test/run commands; conventions (3–7 concrete rules per area); known traps drawn from the real history of sprints 010–012; an explicit never-do list; pointers to deeper docs; a current SPECKIT block.
4. **Given** a fresh agent with only the root CLAUDE.md, **When** it is asked a representative routing question (e.g. "where do I add a new LLM analysis call?"), **Then** the file routes it to the correct module and owning rule file.

---

### User Story 2 - Nested per-module CLAUDE.md files (Priority: P2)

An agent working inside a specific module (e.g. `src/speakloop/llm/`) gets that module's local invariants, extension points, and gotchas loaded on demand — and only those. No rule appears in more than one file; where another file needs the rule, it points to the owning file instead of copying it.

**Why this priority**: Nested files load just-in-time, keeping the launch footprint small while still delivering module-local knowledge exactly when it is needed. Duplication across files is the primary cause of context clash.

**Independent Test**: For each module under `src/speakloop/`, audit its CLAUDE.md (or its absence) against the module's code; run a duplicate-rule scan across all context files against the rule-ownership map.

**Acceptance Scenarios**:

1. **Given** the set of modules under `src/speakloop/`, **When** the audit completes, **Then** each module either has a CLAUDE.md containing only verified local invariants/extension points/gotchas, or has none because it has no real local rules (no empty stubs).
2. **Given** all context files, **When** rules are cross-referenced against the rule-ownership map, **Then** every rule has exactly one owning file and zero duplicated rules exist.
3. **Given** any nested CLAUDE.md, **When** its line count is measured, **Then** it is ≤200 lines.

---

### User Story 3 - Scoped rules and context hygiene (Priority: P3)

Cross-cutting rules that apply only to specific paths live in `.claude/rules/*.md` with `paths` frontmatter so they load only when matching files are touched. Stale context is deleted or archived. @-imports stay sparse and within the documented depth limit. The loaded-memory view confirms the intended files actually load.

**Why this priority**: Path-scoped rules and hygiene reduce per-session token cost and eliminate confusion from stale assets, but they depend on the audits of P1/P2 to know what is genuinely cross-cutting versus module-local.

**Independent Test**: Inspect `.claude/rules/` frontmatter; verify the memory-loading view lists exactly the intended files; grep for stale artifacts.

**Acceptance Scenarios**:

1. **Given** a rule that applies across modules but only to specific paths, **When** placement is decided, **Then** it lives in a single `.claude/rules/*.md` file with `paths` frontmatter.
2. **Given** the finished context layer, **When** the memory-loading view is checked, **Then** the intended files (and only those) load.
3. **Given** the repository after the overhaul, **When** scanned for stale context artifacts, **Then** none remain (deleted or explicitly archived).

---

### User Story 4 - Anti-rot convention (Priority: P4)

A contributor who lands a behavior-changing commit is bound — by the constitution and the root never-do list — to update the owning context file in the same commit. A lightweight guard test fails CI if any CLAUDE.md exceeds 200 lines.

**Why this priority**: Without a binding maintenance rule the overhaul rots again within a few sprints, exactly as it did after 010–012. It is last because it depends on the final shape of the context layer.

**Independent Test**: Read the constitution amendment and root never-do entry; run the guard test against a deliberately oversized temp file fixture expectation (the test logic asserts line counts of every committed CLAUDE.md).

**Acceptance Scenarios**:

1. **Given** the constitution and root CLAUDE.md, **When** read after the overhaul, **Then** both contain the rule: any commit that changes behavior must update the owning context file in the same commit.
2. **Given** the guard test, **When** the full suite runs, **Then** it asserts every CLAUDE.md in the repository is ≤200 lines, and it is the only code addition in the feature.

---

### Edge Cases

- A claim in a context file is contradicted by code → code wins; the claim is fixed or deleted.
- Conflicting guidance between an old spec artifact (`specs/001`–`013`) and current code → code wins; the spec stays untouched as immutable history.
- A claim that cannot be verified against code → deleted (a stale claim is worse than a missing one); if deliberately retained, it is explicitly marked as unverified.
- A module with no CLAUDE.md and no real local rules → no file is created (an empty stub is noise, not context).
- A rule that seems to belong in two places → the ownership map decides one owner; the other location gets a pointer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The root CLAUDE.md MUST be rewritten from the current code, ≤200 lines, containing exactly the guide's sections: 2–3 sentence overview; tech stack as a fixed list; module layout with dependency rules; exact build/test/run commands actually used; conventions (3–7 concrete rules per area); known traps drawn from the real history of sprints 010–012; an explicit never-do list; pointers to deeper docs instead of inlined detail; a current SPECKIT block.
- **FR-002**: Every sentence in every context file MUST be verifiable against the code as it exists today; the audit MUST record file:line evidence per claim with a verdict (accurate / stale-fixed / deleted).
- **FR-003**: Each module under `src/speakloop/` MUST end with either a CLAUDE.md holding only verified local invariants, extension points, and gotchas, or no CLAUDE.md when it has no real local rules. The module list is confirmed during audit, not assumed.
- **FR-004**: No rule may be duplicated: each rule MUST have exactly one owning file recorded in a rule-ownership map; all other references MUST be pointers.
- **FR-005**: Genuinely path-scoped cross-cutting rules MUST move to `.claude/rules/*.md` with `paths` frontmatter; stale context MUST be deleted or archived; @-imports MUST stay sparse and within the documented 5-hop depth limit.
- **FR-006**: The constitution and the root never-do list MUST each gain the anti-rot rule: any commit that changes behavior must update the owning context file in the same commit.
- **FR-007**: A guard test MUST assert every CLAUDE.md in the repository stays ≤200 lines; this is the single permitted code addition.
- **FR-008**: The cumulative diff MUST touch only `*.md` files, `.claude/**`, docs, and the single guard test — nothing else in `src/` or `tests/` beyond the guard test.
- **FR-009**: The full test suite MUST stay green with an unchanged pass count (baseline: 696 passed, 3 skipped, 2 deselected).
- **FR-010**: Six fresh-agent smoke tests (each given only the task text plus the new context) MUST route to the correct files and rules; each verdict MUST be recorded with evidence.
- **FR-011**: A RETURN_REPORT.md at the repo root MUST record: before/after inventory (line + token counts per context file), the claim-audit table, the rule-ownership map, smoke-test verdicts, suite numbers, and merge readiness.

### Key Entities

- **Context artifact**: any agent-facing file — root CLAUDE.md, nested module CLAUDE.md files, `.claude/rules/*.md`, `.claude/` agents/skills/commands/settings, the constitution, docs. Attributes: path, line count, token count, load trigger (launch / on-demand / path-scoped).
- **Claim**: a checkable statement inside a context artifact. Attributes: source file, claim text, code evidence (file:line), verdict (accurate / stale-fixed / deleted).
- **Rule**: a binding instruction with exactly one owning file. Attributes: rule text, owner file, pointer locations.
- **Smoke-test task**: one of six representative routing questions with a pass/fail verdict and evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of claims across all context files are verified against code with file:line evidence; zero stale claims remain.
- **SC-002**: Every CLAUDE.md in the repository is ≤200 lines (enforced by the guard test).
- **SC-003**: Zero duplicated rules: the rule-ownership map exists and every rule resolves to exactly one owner.
- **SC-004**: All six fresh-agent smoke-test tasks pass with recorded evidence.
- **SC-005**: The cumulative git diff is confined to context paths (`*.md`, `.claude/**`, docs) plus the one guard test.
- **SC-006**: The full suite is green with an unchanged pass count (696 passed, 3 skipped, 2 deselected at baseline).

## Out of Scope

- Any production code or test change beyond the single guard test.
- Runtime prompt files under `~/.speakloop/`.
- The `specs/001`–`013` history artifacts — they are immutable records; fix forward in context files, never edit history.
- Renames of code files or modules.
- README marketing copy beyond correcting factual staleness.

## Assumptions

- `doc/research_context_engineering.md` is the binding authority for structure and budgets; where it conflicts with any other instruction in this feature, the guide wins.
- The guard test runs as part of the regular pytest suite and adds new passing tests (the "unchanged pass count" criterion refers to no existing test changing status; the new guard test's own passes are reported separately).
- "Docs" in the diff-scope guard means `doc/`, `docs/` (if present), `README.md`, `CHANGELOG.md`, `RETURN_REPORT.md`, and `specs/014-agent-context-overhaul/**`.
- Token counts in inventories are estimates (chars/4 or equivalent heuristic) — exact tokenizer parity is not required.
- The memory-loading verification uses the best available equivalent of `/memory` in a non-interactive run (e.g. enumerating which files Claude Code loads at launch per its documented loading rules) and is recorded in the report.

## Clarifications

*(to be filled by /speckit-clarify)*
