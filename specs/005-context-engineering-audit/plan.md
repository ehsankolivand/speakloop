# Implementation Plan: Context Engineering Audit & Rewrite of the CLAUDE.md Layer

**Branch**: `005-context-engineering-audit` | **Date**: 2026-05-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-context-engineering-audit/spec.md`

## Summary

Treat speakloop's context layer — the top-level `CLAUDE.md`, the 13 per-module
`CLAUDE.md` files, any `.claude/rules/`, and `doc/research_context_engineering.md` —
as a first-class deliverable governed like code: short, concrete, code-true,
single-source-of-truth. The work is an **audit-then-rewrite**: Phase 0 establishes
ground truth from the code (line counts, import scan, command verification, test
coupling, trap evidence, cross-reference check, footprint measurement); the rewrite
phases then bring every file into a shared anatomy, verified against that ground
truth, with a fresh review sub-agent producing the zero-CRITICAL/MAJOR verdict for
the top-level file. Code is the source of truth; the constitution is the sole
read-only authority and wins on any documentation conflict. No application code
changes, no new dependencies (audit = Python stdlib + `git` + `ripgrep`; review =
the existing Task/general-purpose agent). Delivered iteratively per Principle XII:
US1 (top-level + maintenance section) is the MVP and ships as a coherent slice
before US2 (module files) and US3 (scoped rules + research doc).

## Technical Context

**Language/Version**: Python 3.12 (pinned `requires-python = ">=3.12,<3.13"` in
`pyproject.toml`). This feature changes no Python source; the audit scripts, where
needed, are stdlib-only one-liners.

**Primary Dependencies**: None added. Audit tooling = Python stdlib + `git` +
`ripgrep` (`rg`), all already present. Token measurement uses `tiktoken` invoked
**ephemerally** via `uv run --with tiktoken …` (NOT added to `pyproject.toml`), with
a stdlib `chars / 4` fallback so measurement works offline. Adversarial review uses
the existing Claude Code Task/general-purpose agent — no new system.

**Storage**: Markdown files. Deliverable files: `CLAUDE.md` (root), 13
`src/speakloop/*/CLAUDE.md`, optional `.claude/rules/*.md`,
`doc/research_context_engineering.md`. Audit artifacts persist under
`specs/005-context-engineering-audit/`.

**Testing**: `pytest` (existing suite must stay green; `tests/integration/test_path_portability_audit.py`
is the gate for path leakage). No new tests are created (the engine-isolation test
already exists — see Phase 0). Command verification runs commands directly, not as
new pytest cases.

**Target Platform**: Apple Silicon macOS for the documented project (Principle VII);
the audit and review procedures are platform-agnostic.

**Project Type**: Single-project CLI tool. Documentation/context-layer feature — no
new runtime surface.

**Performance Goals** (the measurable budgets this feature enforces):
- Launch-time context footprint ≤ **6000 tokens** (hard ceiling; see research.md §A).
- Top-level `CLAUDE.md` < 200 lines; each module `CLAUDE.md` < 100 lines.
- Maintenance section readable & applicable in < 2 minutes.

**Constraints**: No application-code changes (FR-053; "trivial" defined in
research.md §G as doc-resident edits only). No new declared dependency. Constitution
is read-only (FR-051). English-only (Principle I). Path-portability audit stays green
(FR-042). Import depth ≤ 5 hops; pointers preferred over `@`-imports (FR-055).
SPECKIT-managed block in the top-level file is preserved (FR-015).

**Scale/Scope**: 14 `CLAUDE.md` files (1 root + 13 modules), 1 research doc, 0–N
scoped rule files (decided in US3), 8 audit deliverables under the feature dir.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Relevance | Status |
|-----------|-----------|--------|
| I. English-Only | All context-layer content must be English (FR-050); research doc sanitized to English (FR-041). | **PASS** — enforced as acceptance criteria. |
| IV. Modular / per-module CLAUDE.md (NON-NEGOTIABLE) | The shared module anatomy *supersets* Principle IV's six fields (FR-031); every module keeps its CLAUDE.md. | **PASS** — feature directly strengthens this. |
| V. Swappable Engines | Import scan verifies each engine package lives in exactly one wrapper (FR-006); documented per module (FR-032). | **PASS** — verified, not assumed (Phase 0 confirms isolation holds). |
| X. Research in Repo | Adds `doc/research_context_engineering.md` as an *additional* reference doc. Principle X mandates the four research files (tts/asr/llm/methodology) as a floor; a fifth reference doc does not conflict. | **PASS** — floor not ceiling; the four mandated files are untouched. |
| XI. AI-Collaborator Friendly | The entire feature exists to minimize loadable context per task and keep seams clear. | **PASS** — core purpose. |
| XII. Iterative Delivery | US1 (MVP) ships before US2/US3 (Phase 3 → 4 → 5). | **PASS** — phasing below. |
| Governance: constitution read-only | FR-051 forbids editing `.specify/memory/constitution.md`. | **PASS**. |

No violations. **Complexity Tracking is empty.** One guideline note (not a
violation): the constitution prefers "standard library over dependencies." Token
measurement therefore uses an ephemeral `uv run --with tiktoken` invocation (no
declared dependency) plus a stdlib `chars / 4` fallback — keeping `pyproject.toml`
clean while still giving a precise cl100k_base count.

## Project Structure

### Documentation (this feature)

```text
specs/005-context-engineering-audit/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature spec (with Clarifications session 2026-05-21)
├── research.md          # Phase 0 recon + 8 audit deliverables + budget + protocols
├── data-model.md        # Entities + the explicit anatomy definitions
├── quickstart.md        # How to run the audit + reproduce the sub-agent review
├── contracts/
│   ├── anatomy-contract.md       # The ordered section spine (top-level + module)
│   └── audit-pass-fail-contract.md  # What "pass" means per FR/SC
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root) — files this feature TOUCHES (docs only)

```text
CLAUDE.md                              # root map — rewritten to top-level anatomy (US1); SPECKIT block preserved
src/speakloop/
├── asr/CLAUDE.md                      # rewritten to module anatomy (US2)
├── audio/CLAUDE.md                    # rewritten + expanded (thin today)
├── cli/CLAUDE.md
├── config/CLAUDE.md
├── content/CLAUDE.md
├── debrief/CLAUDE.md
├── feedback/CLAUDE.md
├── installer/CLAUDE.md
├── llm/CLAUDE.md
├── metrics/CLAUDE.md
├── sessions/CLAUDE.md
├── trends/CLAUDE.md
└── tts/CLAUDE.md
.claude/rules/*.md                     # 0..N, decided in US3 (added only if justified)
doc/research_context_engineering.md    # path-sanitized + English (US3)
```

**Read-only ground-truth inputs (NEVER modified by this feature):**
`src/speakloop/**/*.py`, `tests/**`, `pyproject.toml`, `.specify/memory/constitution.md`,
`specs/001`–`specs/004`, `README.md`.

**Structure Decision**: Single-project CLI; no new directories beyond the optional
`.claude/rules/` and the feature's own `specs/005-…/` artifacts. The deliverables are
documentation files co-located with the code they describe (Principle IV/XI), and the
audit evidence lives under the feature directory following the sprint-3/sprint-4
pattern.

## Phasing (Principle XII — iterative delivery)

Maps to `/speckit-tasks` phases (tasks.md, produced later):

- **Phase 1–2 (Setup + Foundational)**: Phase 0 reconnaissance and the 8 audit
  deliverables in research.md. No file is rewritten until its claims have a
  ground-truth row. Blocks all rewrite phases.
- **Phase 3 — US1 (MVP, P1)**: Rewrite the top-level `CLAUDE.md` to the anatomy +
  the maintenance section; run the fresh review sub-agent to a zero-CRITICAL/MAJOR
  verdict; verify every documented command. **Independently shippable** — delivers a
  trustworthy launch map even if nothing else lands.
- **Phase 4 — US2 (P2)**: Rewrite the 13 module `CLAUDE.md` files to the module
  anatomy; confirm each engine import boundary. Begins only after US1 is a coherent
  slice.
- **Phase 5 — US3 (P3)**: Decide/justify `.claude/rules/*.md` (zero allowed);
  sanitize + commit the research doc; measure and confirm the launch footprint
  within budget. Deliberately last and optional.

US1 is complete and valuable before US2 starts; later phases never break earlier ones.
