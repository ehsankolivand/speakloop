# Test-coupling check (T010) — FR-054, SC-H

Scan: `rg -ln "CLAUDE\.md" tests/`

Result: a single hit — `tests/integration/test_help_without_models.py`. Its reference is a
**docstring comment** ("the cli/CLAUDE.md contract"), NOT a content assertion on any
`CLAUDE.md` file.

**Finding: no test asserts on `CLAUDE.md` content.** The rewrite cannot break a test by
changing prose. No test is weakened (FR-054). The full `pytest` suite is re-run green after the
rewrites (SC-H, gate G8) — see `gate-checklist.md`.
