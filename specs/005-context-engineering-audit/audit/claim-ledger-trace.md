# Claim-ledger trace (T050) — FR-056

Every non-obvious design decision in the rewritten context layer traces to a numbered claim in
`doc/research_context_engineering.md` §17.

| Design decision | §17 claim(s) | Rationale |
|-----------------|--------------|-----------|
| Launch footprint capped ≤ 6000 tokens; push detail down on overflow | 3, 4, 32 | "Smallest set of high-signal tokens"; context rot grows with length; `CLAUDE.md` is dropped in up front. |
| Module `CLAUDE.md` files load on-demand, contribute 0 launch tokens | 6, 13 | Subdirectory files load just-in-time when a file there is read, not at launch. |
| Top-level file is the one re-injected after `/compact` → keep it the trustworthy map | 19 | Project-root `CLAUDE.md` is re-injected after `/compact`; nested files are not. |
| Root file kept < 200 lines | 17 | Official target file size. |
| Human-only "why" notes in HTML comments (zero context cost) | 14 | Block-level HTML comments are stripped before injection. |
| Prefer pointers over `@`-imports; import depth ≤ 5 | 15 | `@`-imports load at launch and cap at depth 5; pointers stay zero-cost. |
| Scoped rules would use `paths` frontmatter (decided: none added) | 22 | `.claude/rules/*.md` supports `paths` globs — the basis for the US3 decision. |
| Fixed 9-section anatomy (organized sections, predictable order) | 5 | Anthropic recommends organizing prompts into labeled sections. |
| Maintenance section exists because `CLAUDE.md` is read every session and must stay true | 10 | The file is read at the start of every session — staleness is paid for every time. |
| Just-in-time module guidance vs. one big file | 6, 32 | Lightweight identifiers + on-demand load beat front-loading everything. |

All decisions trace to a high-confidence official-doc claim (10–22, 32) or the Anthropic
context-engineering post (3, 4, 5, 6) — satisfies FR-056 / gate G15.
