# Implementation Plan: Public Release Readiness

**Branch**: `004-public-release-readiness` | **Date**: 2026-05-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-public-release-readiness/spec.md`

## Summary

Make speakloop cloneable-and-runnable by a stranger. Four slices: (1) relocate the
default questions to a discoverable in-repo file `content/questions.yaml`, with the
prior `~/.speakloop/qa.yaml` becoming an opt-in personal override that wins when
present; (2) a stdlib-only, git-driven path-portability audit wired into the test
suite that fails on any machine-specific absolute path; (3) a rewritten root README
(pitch → platforms/status → install → quickstart → annotated report example → where
things live → contributor links → known limitations → troubleshooting); (4) confirm
the MIT LICENSE is present. No new dependencies; report schema unchanged; the only
behavior change is question-file resolution precedence.

## Technical Context

**Language/Version**: Python 3.12 (constitution: 3.11+, 3.12 recommended)

**Primary Dependencies**: No new runtime dependency (FR-028). The audit uses only
the standard library (`subprocess`, `re`, `pathlib`) plus the already-required `git`.
Question loading reuses the existing `pyyaml` + `speakloop.content` loader.

**Storage**: Filesystem. Default questions at repo `content/questions.yaml`; optional
override at `~/.speakloop/qa.yaml`; reports under `data/sessions/` (unchanged).

**Testing**: pytest. New audit test under `tests/integration/`; existing question/
loader tests must stay green (FR-005) with test-internal fixture migration documented.

**Target Platform**: macOS Apple Silicon, Python 3.12 (stated explicitly in README).

**Project Type**: Single-project local CLI (`src/speakloop/`, `tests/`).

**Performance Goals**: Path-portability audit deterministic and < 2 s (FR-011, SC-G).
README readable end-to-end in ~5 min (FR-020); clone→first report < 15 min excluding
model download (SC-A).

**Constraints**: Offline-first, English-only, `schema_version` stays 1, modular
boundaries preserved, engines untouched, MIT, no GUI (Principles I, II, IV, V, IX;
constraints from constitution).

**Scale/Scope**: Documentation-heavy. One substantive code change (question-file
resolution in `config/paths.py` + `cli/practice.py`); one new test module; one README
rewrite; doc-consistency edits to module `CLAUDE.md` files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Constraint | Status | Note |
|---|---|---|
| I. English-Only UI | ✅ | All README, errors, audit output in English. |
| II. Offline-First | ✅ | Audit reads local git tree only; no network added. |
| III. Privacy by Design | ✅ | Annotated README example is hand-authored generic content — no real recording/name (FR-017). |
| IV. Modular by Design | ✅ | Question resolution stays in `config/` + `cli/`; audit is self-contained in its test module. Each touched module's `CLAUDE.md` updated (FR-026). |
| V. Swappable Engines | ✅ | No engine code touched. |
| VI. Resumable Downloads | ✅ | Untouched; README documents resume in troubleshooting. |
| VII. Apple Silicon Target | ✅ | README states the supported platform. |
| VIII. Easy Install | ✅ | Directly advances this principle: clone→run via README; `--help` still needs no models. |
| IX. Obsidian Reports | ✅ | `schema_version` unchanged; README example mirrors the real frontmatter. |
| X. Research in Repo | ✅ | Engine docs untouched; this feature adds no engine decision. |
| XI. AI-Collaborator Friendly | ✅ | No widening of per-module context; doc updates keep `CLAUDE.md` accurate. |
| XII. Iterative Delivery | ✅ | US1 (questions + README + license) ships as a coherent release on its own; US2–US4 layer on. |
| Constraint: MIT license | ✅ | LICENSE present at root (FR-025/SC-E). |
| Constraint: YAML config | ✅ | Questions remain YAML; override is YAML. |
| Constraint: no new dependency | ✅ | Audit is stdlib + git (FR-028). |

**Result**: PASS. No violations; Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-public-release-readiness/
├── plan.md              # This file
├── research.md          # Phase 0 — resolved decisions
├── data-model.md        # Phase 1 — entities
├── quickstart.md        # Phase 1 — clone→first-report walkthrough (mirrors README)
├── contracts/
│   ├── question-resolution.md   # precedence + error contract
│   └── path-audit.md            # audit input/patterns/output contract
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
content/
└── questions.yaml                 # NEW — discoverable in-repo default question set (migrated)

src/speakloop/
├── config/
│   ├── paths.py                   # CHANGED — default_qa_file() + resolve_qa_file() precedence
│   └── CLAUDE.md                  # CHANGED — document new default + override
├── content/
│   ├── starter.yaml               # REMOVED (or retained only if research keeps a packaged copy)
│   └── CLAUDE.md                  # CHANGED — point at content/questions.yaml + override
└── cli/
    ├── practice.py                # CHANGED — _resolve_qa_file (override precedence, no auto-copy, clear FR-006 error)
    └── CLAUDE.md                  # unchanged unless wording references the copy-on-first-run

tests/
├── integration/
│   ├── test_path_portability_audit.py   # NEW — FR-007..011 / SC-B / SC-G
│   └── (repro_gate_test.py, test_qa_edit_round_trip.py, test_offline_after_install.py …)  # CHANGED — read content/questions.yaml
└── conftest.py                    # CHANGED — first-question fixture reads content/questions.yaml

README.md                          # REWRITTEN — FR-012..024
LICENSE                            # PRESENT — verify MIT (FR-025)
CLAUDE.md                          # CHANGED — Active feature pointer + module-map note for question default
```

**Structure Decision**: Existing single-project layout retained. The one new
runtime artifact is the top-level `content/questions.yaml`, chosen to match the
existing cwd-relative convention already used by `paths.sessions_dir()`
(`Path.cwd()/data/sessions`) and to be discoverable without reading source. The
audit lives entirely inside its test module to avoid introducing a new shipped
module for a CI-only check.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
