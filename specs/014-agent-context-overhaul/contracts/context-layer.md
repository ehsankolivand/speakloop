# Contract — the SpeakLoop context layer (014)

The interface this feature exposes is the set of files an agent loads. This contract
fixes their shape so the guard test and future features can rely on it.

## File contract

| File | Sections (in order) | Budget |
|---|---|---|
| `CLAUDE.md` (root) | SPECKIT block (markers kept) · Overview (2–3 sentences) · Tech stack (fixed list) · Module layout + dependency rules · Commands · Conventions · Traps · Never do · Maintenance (anti-rot, ≤5 lines) · Pointers | ≤200 lines |
| `src/speakloop/<mod>/CLAUDE.md` ×19 | Purpose (1–2 lines) · Public interface · Local invariants & traps · Extension points ("how to add X") · Pointers | ≤200 lines (target ≤70) |
| `.claude/rules/testing.md` | frontmatter `paths: ["tests/**"]` · test rules (owner O9) | ≤60 lines |
| `.claude/rules/llm-calls.md` | frontmatter `paths:` the 5 LLM-caller module globs · LLM-call rules (owners O7, O8) | ≤60 lines |
| `.specify/memory/constitution.md` | +1 Development Guideline (anti-rot, O16); version 1.1.0; Sync Impact Report updated | — |

## Guard test contract

`tests/integration/test_context_file_budget.py`:
- discovers every git-tracked `CLAUDE.md` (root + nested) via `git ls-files`
  fallback to `Path.rglob` excluding `.venv`/`node_modules`;
- asserts `line_count <= 200` per file with the offending path in the failure message;
- stdlib + pytest only; runs in the default suite (no marker).

## Pointer syntax contract

Plain repo-relative paths in prose or links — e.g. "see `src/speakloop/llm/CLAUDE.md`".
Never `@path` imports. One hop: a pointer's target must itself contain the rule.
