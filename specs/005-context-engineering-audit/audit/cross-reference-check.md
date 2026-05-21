# Cross-reference link check (T009; re-verified T023/T041) — FR-005, SC-J

Every `[text](path)` and bare `path/` pointer in the `CLAUDE.md` layer resolved against the
filesystem.

## Root `CLAUDE.md`
- 13 module links (`src/speakloop/<mod>/CLAUDE.md`) — **all resolve** ✅
- `doc/research_tts.md`, `doc/research_asr.md`, `doc/research_llm.md` — **all resolve** ✅
- `specs/001`…`specs/005` plan/spec pointers — resolve ✅
- `.specify/memory/constitution.md` — resolves ✅

## Module `CLAUDE.md` files
- No markdown-link pointers existed in module files (bare-text references only).
- `asr/CLAUDE.md` bare refs `doc/research_asr.md`, `doc/research_asr_l2_accent.md` — resolve ✅

## doc/research_context_engineering.md
- Internal section references (e.g. "§17") resolve to `## 17. Sources and claim ledger` (line 523) ✅

**Result: zero broken cross-references.** All pointers added in the rewrite (root + modules)
are re-checked in T041; new pointers introduced point only to verified existing files.
