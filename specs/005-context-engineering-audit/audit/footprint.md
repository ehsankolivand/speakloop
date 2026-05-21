# Launch-footprint measurement (T012 baseline; T045 final) — FR-043, SC-K

Budget: launch-time context layer **≤ 6000 tokens** (cl100k_base). Counts the top-level
`CLAUDE.md` + any UNSCOPED `.claude/rules/*.md` + any `@`-imports. Module `CLAUDE.md` files and
`paths`-scoped rules contribute **zero** (loaded just-in-time).

| Measurement | tiktoken (cl100k_base) | stdlib `chars/4` proxy | Ceiling | OK? |
|-------------|------------------------|------------------------|---------|-----|
| Baseline (T012, pre-rewrite) | 1522 tokens | 5333 chars ≈ 1333 | 6000 | ✅ |
| Final (T045, post-rewrite)   | see gate-checklist.md (G11) | — | 6000 | ✅ |

**Zero-launch confirmation:**
- `.claude/rules/` does not exist (no unscoped rules) — confirmed `ls .claude/rules/` → absent.
- No `@`-imports in any `CLAUDE.md` — confirmed `rg "^@|]\(@" CLAUDE.md src/speakloop/*/CLAUDE.md` → none.
- The 13 module `CLAUDE.md` files load on-demand only → 0 launch tokens.

Command (primary): `uv run --with tiktoken …` (tiktoken NOT added to pyproject — ephemeral).
Fallback (offline): `uv run python -c "import pathlib;c=len(pathlib.Path('CLAUDE.md').read_text());print(c//4)"`.
