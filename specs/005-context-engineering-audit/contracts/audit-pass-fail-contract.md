# Contract: Audit Pass/Fail Gates

**Feature**: 005-context-engineering-audit

The feature is **done** iff every gate below is satisfied. Each maps to a success
criterion / functional requirement and a concrete check.

| Gate | Check (how to verify) | Pass condition | Maps to |
|------|------------------------|----------------|---------|
| G1 line ceilings | `find . -name CLAUDE.md \| xargs wc -l` | root < 200, every module < 100 | SC-A, FR-013, FR-033 |
| G2 anatomy order | Inspect each file vs anatomy-contract.md | Conforms for its scope | SC-B, FR-010, FR-030, FR-031 |
| G3 adversarial review | Run the review sub-agent (research §I) on root `CLAUDE.md` | VERDICT = PASS (0 CRITICAL, 0 MAJOR); every claim traces to `file:line` | SC-C, FR-014 |
| G4 traps | Count + evidence-check root `traps` | ≥ 5 entries, each with commit / session-report / `specs/` evidence | SC-D, FR-004, FR-011 |
| G5 maintenance | Read the maintenance section | Concrete rules, < 2 min, feature-driven cadence stated | SC-E, FR-020 |
| G6 research doc | `uv run pytest tests/integration/test_path_portability_audit.py` | Green; no `/Users/...` in `doc/research_context_engineering.md`; English | SC-F, FR-041, FR-042 |
| G7 scoped rules | Inspect any `.claude/rules/*.md` | Each has `paths` frontmatter + HTML-comment justification; OR none added + decision recorded | SC-G, FR-040 |
| G8 suite green | `uv run pytest` | All pass; no test broke from CLAUDE.md changes; any content-asserting test flagged (none found — research §H) | SC-H, FR-053, FR-054 |
| G9 commands | Run every documented command | Each `verified`; failing/missing removed; undocumented-but-real added | SC-I, FR-003, FR-012 |
| G10 cross-refs | Resolve every pointer | Zero broken links in live `CLAUDE.md` files | SC-J, FR-005 |
| G11 footprint | Run footprint command (research §A) | Launch footprint ≤ 6000 tokens; module files + `paths`-scoped rules = 0 launch tokens | SC-K, FR-043 |
| G12 engine isolation | Run import scan (research §C) | Each **directly-imported** engine package (`mlx_whisper`, `silero_vad`, `parakeet_mlx`, `mlx_lm`, `kokoro_mlx`) → exactly one wrapper file, recorded; `onnxruntime` recorded as transitive-via-silero (D-1), NOT required to have an owning wrapper | SC-L, FR-006 |
| G13 no code changes | `git diff --name-only` | Only `*.md` + `.claude/rules/` touched; no `src/**/*.py`, `tests/**`, `pyproject.toml` | FR-053 |
| G14 read-only inputs | `git diff` | `.specify/memory/constitution.md` and `specs/001`–`004` unchanged | FR-051, FR-052 |
| G15 claim-ledger trace | Inspect non-obvious decisions | Each traces to a `doc/research_context_engineering.md` §17 claim number | FR-056 |
| G16 FR-055 compliance | `rg "^@\|]\(@" CLAUDE.md src/speakloop/*/CLAUDE.md`; trace any `@`-import chain depth; check why-notes are in HTML comments | No `@`-import chain exceeds 5 hops; pointers are used in preference to `@`-imports; human-only "why" notes and rule justifications live in HTML comments (zero context cost) | FR-055 |

**Severity scale (G3)**: CRITICAL = false claim that would mislead an agent into a wrong
change; MAJOR = materially inaccurate; MINOR = imprecise but not misleading; INFO = note.
Only CRITICAL/MAJOR block the gate.

**Code-change findings**: any divergence whose fix requires editing `src/`, `tests/`, or
`pyproject.toml` is recorded as a divergence row with `action = flag-and-defer` and does
NOT block this feature (FR-053); the doc is written to match current code.
