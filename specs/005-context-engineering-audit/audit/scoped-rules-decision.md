# Scoped-rules decision (T042) — FR-040, SC-G

**Decision: add ZERO `.claude/rules/*.md` files.**

## Investigation

- `.claude/rules/` does not exist today; there are no `@`-imports in any `CLAUDE.md`
  (`rg "^@|]\(@" CLAUDE.md src/speakloop/*/CLAUDE.md` → none).
- Launch footprint after the rewrite is **3341 tokens**, well under the 6000 ceiling — there is
  no budget pressure that a `paths`-scoped rule would relieve.
- The recurring per-module concerns (engine-import isolation, function-local imports, the
  torchaudio pin, Q&A precedence, `schema_version`) are already captured where the work happens:
  in the relevant module `CLAUDE.md` (loaded on-demand) and in the top-level traps/never-do.
- No observed session friction requires a cross-cutting glob rule that does not fit naturally in
  an existing `CLAUDE.md`.

## Rationale

Adding rule files speculatively would violate the very discipline this feature enforces (only
add context that earns its place). A module `CLAUDE.md` already loads exactly when a file in that
module is read — the same just-in-time scoping a `paths`-scoped rule would provide — so a rule
file would be redundant. If a future need arises (e.g. a convention spanning files in several
modules), the maintenance checklist item #7 covers adding one with `paths` frontmatter + an
HTML-comment justification at that time.

**Result:** none added; decision recorded here (satisfies FR-040 / SC-G / gate G7).
