# Contract: CLAUDE.md Anatomy

**Feature**: 005-context-engineering-audit

A `CLAUDE.md` file **conforms** to this contract iff it satisfies every MUST below for
its scope. This is the structural acceptance gate for FR-010, FR-030, FR-031, SC-B.

## Top-level `CLAUDE.md` (scope = root)

- MUST preserve the `<!-- SPECKIT START -->`…`<!-- SPECKIT END -->` block at the top of
  the file, intact and machine-updatable (FR-015).
- MUST present the human-authored region in this exact section order:
  `overview → tech-stack → layout → commands → conventions → maintenance → traps →
  never-do → pointers`.
- All nine sections MUST be present and non-empty.
- `tech-stack` MUST list only entries derived from `pyproject.toml` and confirmed by an
  actual import (no aspirational deps).
- `layout` MUST reflect the import-scan dependency graph, not prose copied from elsewhere.
- `commands` MUST contain only commands with `status = verified` in the command matrix.
- `traps` MUST contain ≥ 5 entries, each with an evidence reference.
- `never-do` entries SHOULD cite a code pattern where one applies.
- `maintenance` MUST state the feature-driven cadence + the 7-item checklist and be
  applicable in < 2 minutes.
- MUST be < 200 lines, entirely English.
- MUST pass the sub-agent adversarial review with **0 CRITICAL, 0 MAJOR** (research §I).

## Module `CLAUDE.md` (scope = module:<name>)

- MUST present sections in this order, omitting only the optional tail when empty:
  `purpose → public-interface → dependencies → consumers → file-map →
  modification-patterns → [traps] → [never-do] → [pointers]`.
- Sections `purpose, public-interface, dependencies, consumers, file-map,
  modification-patterns` are MANDATORY (these are Principle IV's six fields).
- Sections `traps, never-do, pointers` are OPTIONAL and included ONLY when they carry
  real content — never padded with "N/A" (Q1 clarify decision: module-adapted order).
- A module that owns an engine package (`asr`, `llm`, `tts`) MUST name the engine-import
  boundary in `dependencies` (FR-032), matching the owner map in research §C.
- MUST be < 100 lines, entirely English.
- MUST NOT be rewritten unless the module was read in full (its `__init__.py` + primary
  public entry points), recorded in the module-read list (FR-002, FR-034).

## Cross-scope invariants

- Same spine slot appears in the same relative position across all files (SC-B).
- Every cross-reference resolves to an existing target (SC-J).
- Pointers preferred over `@`-imports; import depth ≤ 5 hops (FR-055).
- Human-only "why" notes and rule justifications live in HTML comments (zero context
  cost) (FR-055).
