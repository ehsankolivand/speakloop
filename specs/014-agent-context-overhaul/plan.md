# Implementation Plan: Agent Context Overhaul

**Branch**: `014-agent-context-overhaul` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-agent-context-overhaul/spec.md`

## Summary

Rewrite SpeakLoop's agent-facing context layer (root CLAUDE.md, 19 module CLAUDE.md
files, new `.claude/rules/`) so that every claim is verified against the current code
and the layer follows `doc/research_context_engineering.md` (binding checklist B1–B14
in research.md). Phase 0 audited 375 claims across 21 files and found 58 stale + 9
unverifiable; the implementation fixes or deletes every one, de-duplicates rules per
the ownership map (O1–O18), adds two path-scoped rules files, amends the constitution
with the anti-rot rule (1.0.0 → 1.1.0), and adds one guard test (every CLAUDE.md ≤200
lines) as the single permitted code addition. Zero production-code changes.

## Technical Context

**Language/Version**: Markdown + Python 3.12 (guard test only)

**Primary Dependencies**: none new (guard test = stdlib + pytest already present)

**Storage**: N/A (documentation files in-repo)

**Testing**: `uv run pytest` — baseline 696 passed / 3 skipped / 2 deselected must hold; +1 new guard test

**Target Platform**: repo context layer (Claude Code loading rules per guide §7)

**Project Type**: documentation/context feature

**Performance Goals**: launch footprint = root CLAUDE.md ≤200 lines (~3.5k tokens, down from 298 lines / ~5.3k)

**Constraints**: diff confined to `*.md`, `.claude/**`, `specs/014-*/**`, and the one guard test; specs/001–013 immutable; `~/.speakloop` runtime prompts untouched

**Scale/Scope**: 21 context artifacts audited; 19 module files + root rewritten; 2 rules files created; 1 constitution amendment; 1 guard test

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-checked post-design — PASS.*

- **Principle IV (per-module CLAUDE.md, NON-NEGOTIABLE)**: all 19 module files kept and
  rewritten; none deleted (spec clarification 6 resolved the conflict with the guide's
  delete-as-noise in the constitution's favor).
- **Principle XI (AI-collaborator friendly)**: the feature's whole point — smaller,
  truer context per module. No change widens required context.
- **Principle X (research in repo)**: no engine change → no research_*.md change
  required; the binding guide already lives in doc/.
- **Governance (amendment procedure)**: anti-rot rule lands via proper amendment —
  version line 1.0.0 → 1.1.0 (MINOR), Sync Impact Report updated, dependent artifact
  (root CLAUDE.md never-do) updated in the same commit.
- **Development guideline "every module ships its own CLAUDE.md"**: unchanged, satisfied.
- **Session files untouched / src/ .py untouched / suite behavior identical**: enforced
  by the diff-scope guard each phase.

## Project Structure

### Documentation (this feature)

```text
specs/014-agent-context-overhaul/
├── plan.md              # this file
├── spec.md              # + Clarifications (6 Q→A)
├── research.md          # B1–B14 checklist · inventory · audit summary · O1–O18 ownership map · D1–D10 decisions
├── audit/claim-audit.md # full claim table (375 claims, file:line evidence)
├── data-model.md        # ContextArtifact / Claim / Rule / SmokeTask + invariants
├── contracts/context-layer.md  # file shapes, guard-test contract, pointer syntax
├── quickstart.md        # verification commands
└── tasks.md             # /speckit-tasks output
```

### Touched paths (repository root)

```text
CLAUDE.md                                      # rewrite ≤200 lines (US1)
src/speakloop/<19 modules>/CLAUDE.md           # rewrite each (US2)
.claude/rules/testing.md                       # new, paths: tests/** (US3)
.claude/rules/llm-calls.md                     # new, paths: 5 caller modules (US3)
.specify/memory/constitution.md                # anti-rot amendment 1.1.0 (US4)
tests/integration/test_context_file_budget.py  # the single permitted code addition (US4)
README.md                                      # 4 factual staleness fixes only
RETURN_REPORT.md                               # final report (repo root)
```

**Structure Decision**: flat in-place rewrites; no new directories beyond
`.claude/rules/`. Nested files rely on Claude Code's documented on-demand loading —
root never imports them (no `@`-imports anywhere, decision D4).

## Phase ordering for implementation

1. **Foundational**: guard test (red against current 298-line root, then green after US1 —
   actually written to pass only post-rewrite, so it lands in the same commit as US1's
   root rewrite to keep the suite green at every commit).
2. **US1** root CLAUDE.md rewrite (from audit evidence only).
3. **US2** 19 module rewrites (audit fixes + de-dup per O-map; one task per file).
4. **US3** rules files + README factual fixes + stale-content removal.
5. **US4** constitution amendment.
6. **Verification**: smoke tests ×6, /memory, diff-scope, full suite, RETURN_REPORT.md.

## Complexity Tracking

No constitution violations to justify.
