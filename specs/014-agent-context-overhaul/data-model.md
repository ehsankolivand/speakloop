# Data Model — Agent Context Overhaul (014)

No runtime data. The "data" of this feature is the context layer itself.

## Entities

### ContextArtifact
| Field | Type | Notes |
|---|---|---|
| path | repo-relative path | e.g. `CLAUDE.md`, `src/speakloop/llm/CLAUDE.md`, `.claude/rules/testing.md` |
| kind | root / nested / rule / constitution / doc | |
| load_trigger | launch / on-demand / path-scoped / reference | per guide §7, §13 |
| line_count | int | invariant: ≤200 for every CLAUDE.md (guard test) |
| token_estimate | int | chars/4 |

### Claim
| Field | Type | Notes |
|---|---|---|
| source | ContextArtifact path | |
| text | short quote | |
| evidence | `file:line` in current code | required for verdict `accurate` |
| verdict | accurate / stale-fixed / deleted | end state after implementation; no claim may remain `stale` |

Lifecycle: audited (Phase 0) → fixed-or-deleted (implementation) → re-verified
(adversarial review).

### Rule
| Field | Type | Notes |
|---|---|---|
| id | O1…O18 | from research.md §4 |
| owner | exactly one ContextArtifact | invariant: single home |
| pointers | list of artifacts | one hop max; plain paths, no @-imports |

### SmokeTask
| Field | Type | Notes |
|---|---|---|
| id | SM1…SM6 | the six routing questions from the feature brief |
| input | task text only (no conversation history) | |
| verdict | pass / fail | with recorded evidence |

## Invariants

1. Every CLAUDE.md ≤200 lines (guard test enforces).
2. Every Rule has exactly one owner; a grep for the rule's distinctive phrasing
   matches one file (plus pointer lines naming the owner).
3. Every Claim in a shipped context file has verdict `accurate` with evidence.
4. Pointer chains resolve in one hop.
5. The diff after implementation touches only: `*.md`, `.claude/**`,
   `tests/integration/test_context_file_budget.py`, `specs/014-*/**`.
