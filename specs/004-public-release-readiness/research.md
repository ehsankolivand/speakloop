# Phase 0 Research: Public Release Readiness

All open questions from the spec resolved below. No `NEEDS CLARIFICATION` remain.

## R1 — Default in-repo question location

**Decision**: Ship the default questions at top-level `content/questions.yaml`,
resolved relative to the repository root (the current working directory in the
`git clone && uv run speakloop` workflow).

**Rationale**:
- Discoverability (FR-001, SC-F): a top-level `content/` directory is found without
  reading source, unlike the buried packaged resource `src/speakloop/content/starter.yaml`.
- Consistency: `paths.sessions_dir()` already defaults to `Path.cwd()/data/sessions`,
  so a cwd-relative `content/questions.yaml` matches an established repo convention and
  the constitution's "clone and `uv run`" install model (Principle VIII).
- Editability without a home-directory path (SC-F): the file lives in the checkout.

**Alternatives considered**:
- *Keep packaged `starter.yaml` and copy to `~/.speakloop/qa.yaml` on first run* (status
  quo). Rejected: the user must read source to find the questions, and the only editable
  copy lives under a home-directory path — both contrary to SC-F/FR-001.
- *`src/speakloop/content/questions.yaml`* (in-package, discoverable-ish). Rejected:
  still inside `src/`, less discoverable than a root `content/`; and editing package
  data is unidiomatic.
- *Resolve relative to the installed package via `importlib.resources`*. Rejected for
  the default path because it points at read-only wheel data, defeating "edit in repo";
  the cwd-relative repo file is the editable source of truth. (A package-relative
  fallback was considered for robustness but rejected as cleverness the clone workflow
  does not need — "boring over novel".)

## R2 — Override precedence and opt-in semantics

**Decision**: Resolution order is (1) explicit `--qa-file PATH` (existing flag,
unchanged), (2) `~/.speakloop/qa.yaml` if it exists (personal override, opt-in by
presence), (3) repo `content/questions.yaml` (default). No file is auto-created.

**Rationale**:
- Preserves existing users (Assumption): the prior home path keeps working as an
  override (FR-003).
- Opt-in by presence is the simplest deterministic rule (FR-003, edge case "both
  exist → override wins") and removes the silent first-run *copy* that made the home
  path the only editable source.
- `--qa-file` already overrides via `paths.set_qa_file_path()`; keeping it on top of
  the precedence chain means existing tests and power-user invocations are unaffected.

**Alternatives considered**:
- *Keep auto-copying starter → `~/.speakloop/qa.yaml`*. Rejected: it reintroduces the
  "only editable copy is under home" problem and makes "override is opt-in" false.
- *Environment variable for the default*. Rejected: no new config surface needed; YAML
  + flag already cover it (constitution: YAML-only user config).

## R3 — Migration of existing questions and packaged `starter.yaml`

**Decision**: Move the four questions verbatim from `src/speakloop/content/starter.yaml`
to `content/questions.yaml` with byte-for-byte schema fidelity (FR-004), then remove the
packaged `starter.yaml`. Update the three test touchpoints that read the packaged
resource (`tests/conftest.py` first-question fixture, `tests/integration/repro_gate_test.py`,
and any offline-install test) to read `content/questions.yaml`.

**Rationale**:
- Single source of truth (no duplication / drift).
- FR-005 protects the *loader public signature* `loader.load(path) -> QAFile`, which is
  unchanged. The fixture reads are test-internal; updating them is the "explicitly
  documented migration" FR-005 permits.

**Alternatives considered**:
- *Keep both files in sync*. Rejected: two sources of truth violate "no loss of fidelity"
  in spirit and invite drift.
- *Symlink*. Rejected: not portable across the platforms a wheel might land on, and
  surprising to a reader.

## R4 — Behavior when no question file is found (FR-006)

**Decision**: When neither the override nor `content/questions.yaml` is present/readable,
print one English, actionable message naming both candidate locations and exit non-zero —
no crash, no empty session.

**Rationale**: Matches the existing `QALoadError` "file not found" style in
`content/loader.py`; consistent error UX (Principle I, VIII).

## R5 — Path-portability audit: mechanism, patterns, false-positive avoidance

**Decision**: A stdlib-only audit that (a) enumerates tracked files via
`git ls-files -z`, (b) reads each text file, (c) flags lines matching machine-specific
home-directory patterns, (d) excludes generic/portable references, (e) on any match
fails and prints `path:line` for each offender. Runs as a pytest test under
`tests/integration/`; logic lives in the test module (no new shipped module).

**Patterns flagged** (case-sensitive where the OS is):
- POSIX: `/Users/<name>/…` and `/home/<name>/…` where `<name>` is a concrete login
  (regex `(/Users/|/home/)[A-Za-z0-9._-]+/`).
- Windows: `C:\Users\<name>\…` (regex `[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\`).

**Portable references explicitly NOT flagged** (FR-009, edge case):
- `~/…` and `~/.speakloop/…` (tilde home — portable by construction).
- Placeholder forms with angle brackets: `/Users/<name>/`, `/home/<user>/`,
  `C:\Users\<name>\` (documentation placeholders).
- The audit's own pattern-definition file/lines (self-reference) — excluded by skipping
  the audit module path and by the placeholder rule.
- Binary/non-text files (skipped via decode guard) and the `.git` directory (already
  excluded by `git ls-files`).

**Rationale**:
- `git ls-files` scopes the audit to tracked content exactly as FR-007 requires
  (source, tests, docs, specs, content, root config) and excludes generated/ignored
  files deterministically.
- Pure stdlib honors FR-028 (no new dependency); `git` is already mandated.
- Concrete-login vs `<placeholder>`/`~` distinction is what prevents the false positives
  that would block legitimate documentation (FR-009).

**Performance (FR-011, SC-G)**: The tree is small (low hundreds of tracked files);
a single `git ls-files` plus per-file regex scan completes well under 2 s. The test
asserts a wall-clock budget to guard regressions.

**Self-test (FR-008, SC-B)**: The test also verifies the detector positively — feeding
it a synthetic line containing a concrete `/Users/<concrete>/` path returns a hit — so
the gate cannot silently degrade to "always passes".

**Alternatives considered**:
- *`grep`/`ripgrep` shelling out*. Rejected: ripgrep is not guaranteed present (would be
  a de-facto dependency); the regex set is small enough for `re`.
- *A standalone `scripts/audit_paths.py` + pre-commit hook*. Rejected for v1 scope: the
  spec scopes the gate to the existing test suite (Assumption: "no new CI/CD setup");
  keeping it a test is the smallest thing that satisfies SC-B.

## R6 — Current-tree leak status

**Decision**: No remediation edits required for FR-010 — a scan of the current tree
(`git grep` for `/Users/<name>/` and `/home/<name>/`) found zero machine-specific
absolute-path leaks across source, tests, docs, specs, and content. The audit therefore
passes on the current tree at introduction.

**Rationale**: Verified during planning. Should any leak surface once the full pattern
set runs in-suite, it is removed in the same change that adds the audit.

## R7 — README content sourcing (annotated example, limitations, troubleshooting)

**Decision**: Hand-author all README content. The annotated report example is synthetic
(generic question id, invented transcript fragment, no real name/recording — FR-017),
but its *structure* mirrors the real frontmatter: a top-level `asr:` provenance block
(`engine`, `model`, `fell_back`), at least one grammar pattern, and a `top_priority`
line. Troubleshooting facts are drawn from the actual code/specs:

| Failure mode | Authoritative source in repo | Fix / statement |
|---|---|---|
| Model download failed mid-way | `installer/` resumable download (Principle VI) | re-run resumes; proxy/network-restricted note |
| LLM feedback degraded to fluency-only | `feedback/frontmatter.py` field `phase_c_error`; `cli/practice.py` `_build_grammar_analyzer` returns None when Qwen absent | which field records the cause + what each cause means |
| Technical term misheard | `asr/` domain biasing (`initial_prompt`), `asr:` provenance block; spec 003 | how per-session biasing works + how to add domain terms; known v1 limitation |
| VAD version conflict | `silero-vad` pin in `pyproject.toml`; `asr/vad.py` | why pinned; recover by reinstalling the pinned version via `uv sync` |
| Mic permission on macOS first run | `audio/devices.default_input()` precheck in `practice.py`; `doctor` | grant Microphone permission in System Settings; `speakloop doctor` |
| Recording loop hangs at final attempt | `sessions/coordinator.py` reader/ticker join + `sessions/abort.py` SIGINT handler | interim Ctrl-C abort workaround; explicit "known, deferred" note (Assumption: hang fix out of scope) |

**Rationale**: Honesty (FR-021, FR-024) and accuracy require each entry to map to a
real mechanism; sourcing from code/specs prevents inventing behavior. Generic example
content satisfies Privacy by Design (Principle III, FR-017).

**Alternatives considered**:
- *Capture a real session report for the example*. Rejected: would embed real recording
  metadata/name (FR-017 violation).

## R8 — Internal-doc consistency scope (FR-026)

**Decision**: Update the canonical guidance files that describe the live default —
`src/speakloop/content/CLAUDE.md`, `src/speakloop/config/CLAUDE.md`, and the top-level
`CLAUDE.md` — to state `content/questions.yaml` as the default and `~/.speakloop/qa.yaml`
as the override. Historical specs (001) are left as the record of what they built, with
no rewrite, because they document the state at their own time; the current README and
module `CLAUDE.md` files are the authoritative live references.

**Rationale**: FR-026 targets guidance a contributor relies on now; rewriting frozen
historical specs would falsify the record and is not needed for SC-C/SC-F.
