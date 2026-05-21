# Audit evidence — Context Engineering Audit (005)

Ground-truth artifacts produced from the code, before/while rewriting the `CLAUDE.md`
layer. Code is the source of truth (FR-001). Files in this directory:

| File | Deliverable | Tasks | FR / SC |
|------|-------------|-------|---------|
| `baseline-pytest.txt` | Pre-edit suite + git baseline | T001 | SC-H |
| `toolchain.txt` | Tool versions | T003 | — |
| `engine-import-scan.md` | Engine-import owner map (Principle V) | T004 | FR-006, SC-L |
| `claude-md-inventory.md` | Line counts vs ceilings | T005, T041 | SC-A |
| `module-read-list.md` | Per-module read summary + dependency graph | T006 | FR-002, FR-007, FR-034 |
| `command-matrix.md` | Documented commands run + status | T007, T025, T044 | FR-003, FR-012, SC-I |
| `trap-evidence.md` | Evidence-cited known traps | T008 | FR-004, FR-011, SC-D |
| `cross-reference-check.md` | Pointer resolution check | T009, T023, T041 | FR-005, SC-J |
| `test-coupling.md` | Tests asserting on CLAUDE.md content | T010 | FR-054, SC-H |
| `divergence-inventory.md` | Claim-vs-code divergences | T011, T027, T041, T051 | FR-001 |
| `footprint.md` | Launch-token measurement | T012, T045 | FR-043, SC-K |
| `adversarial-review-verdict.md` | Sub-agent review verdict | T026, T027 | FR-014, SC-C |
| `scoped-rules-decision.md` | `.claude/rules/` decision | T042 | FR-040, SC-G |
| `claim-ledger-trace.md` | Decision → research §17 mapping | T050 | FR-056 |
| `gate-checklist.md` | G1–G16 final gate walk | T051, T052 | all |
