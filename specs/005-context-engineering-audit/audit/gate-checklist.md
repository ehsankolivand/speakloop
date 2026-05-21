# Gate checklist (T051) — G1–G16 from contracts/audit-pass-fail-contract.md

| Gate | Check | Result |
|------|-------|--------|
| G1 line ceilings | `find . -name CLAUDE.md \| xargs wc -l` | ✅ root 187 < 200; every module ≤ 68 < 100 |
| G2 anatomy order | inspect each file vs anatomy-contract.md | ✅ root has 9 sections in order; modules follow module-adapted order, Principle IV six fields present |
| G3 adversarial review | review sub-agent on root `CLAUDE.md` | ✅ PASS (0 CRITICAL, 0 MAJOR) on pass 3 — see adversarial-review-verdict.md |
| G4 traps | count + evidence | ✅ 6 traps, each cites commit/`file:line`/`specs/` — see trap-evidence.md |
| G5 maintenance | read maintenance section | ✅ 7-item checklist, feature-driven cadence, < 2 min, concrete |
| G6 research doc | path-portability test + grep | ✅ `4 passed`; no `/Users/...` in research doc; English |
| G7 scoped rules | inspect `.claude/rules/` | ✅ none added; decision recorded — scoped-rules-decision.md |
| G8 suite green | `uv run pytest` | ✅ 306 passed, 3 skipped (matches baseline) |
| G9 commands | run every documented command | ✅ all 5 documented commands verified; `ruff check .` excluded (D-7) — command-matrix.md |
| G10 cross-refs | resolve every pointer | ✅ zero broken links — cross-reference-check.md |
| G11 footprint | footprint command | ✅ 3302 tokens ≤ 6000; module files + (no) scoped rules = 0 launch tokens |
| G12 engine isolation | import scan | ✅ each of mlx_whisper/silero_vad/parakeet_mlx/mlx_lm/kokoro_mlx → one wrapper; onnxruntime transitive (D-1) — engine-import-scan.md |
| G13 no code changes | `git diff --name-only` | ✅ only `*.md` touched; no `src/**/*.py`, `tests/**`, `pyproject.toml` (`.specify/feature.json` is the pre-existing workflow tracker, not code) |
| G14 read-only inputs | `git diff` | ✅ constitution + specs/001–004 unchanged |
| G15 claim-ledger trace | inspect decisions | ✅ each non-obvious decision → §17 claim — claim-ledger-trace.md |
| G16 FR-055 compliance | `rg "^@\|]\(@"` + import depth | ✅ no `@`-imports (pointers only); why-notes in HTML comments |

**All 16 gates PASS.** Two findings deferred (code changes out of scope, FR-053): D-3
(no kokoro_mlx isolation test) and D-7 (`ruff check .` has pre-existing findings). Neither blocks
any gate; docs are written to match current code.

## Quickstart validation (T052)

`specs/005-context-engineering-audit/quickstart.md` reproduced end to end:
- §1 reconnaissance (line counts, engine scan, `/Users/` grep clean, test-coupling) — matches audit artifacts.
- §2 command verification — 5 commands verified (command-matrix.md).
- §3 footprint — 3302 tokens (footprint.md).
- §4 adversarial review — PASS recorded (adversarial-review-verdict.md).
- §5 gates — path-portability green; `git diff --name-only` shows only `*.md`.
- §6 maintenance checklist — present in the top-level `CLAUDE.md`.

Audit reproduces; feature is **done**.
