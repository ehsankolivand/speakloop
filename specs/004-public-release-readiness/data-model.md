# Phase 1 Data Model: Public Release Readiness

This feature adds no new persisted schema and does **not** change the session-report
frontmatter (`schema_version` stays 1). The "entities" below are configuration and
document structures, not new stored records.

## E1 — Question set (resolution model)

The collection of practice questions plus the rule for locating the active file.

| Field / location | Type | Source | Notes |
|---|---|---|---|
| `content/questions.yaml` | YAML file (repo, cwd-relative) | NEW default | Migrated from `src/speakloop/content/starter.yaml`; same `QAFile` schema (`schema_version: 1`, `questions: [...]`). |
| `~/.speakloop/qa.yaml` | YAML file (home) | optional override | Opt-in by presence; wins over the default. |
| `--qa-file PATH` | CLI flag → `paths.set_qa_file_path()` | explicit override | Highest precedence; existing behavior unchanged. |

**Schema** (unchanged, per `specs/001-v1-product-spec/contracts/content-schema.yaml`):
`QAFile { schema_version: 1, questions: [ Question{ id, question, ideal_answer, tags?, difficulty?, voice_override? } ] }`. Loaded and validated by `content/loader.load(path)`.

**Resolution rule** (precedence, first match wins):
1. `--qa-file PATH` if supplied.
2. `~/.speakloop/qa.yaml` if it exists and is readable.
3. `content/questions.yaml` (repo default).
4. Otherwise → actionable error (E5).

**Validation**: the resolved file is parsed/validated exactly as today; parse and
schema errors keep surfacing `file:line` / `entry id + field` (FR-029/FR-030, existing).

**State transitions**: none. Resolution is a pure function of which files exist plus
the optional flag.

## E2 — Front-page README

Single document a first-time visitor reads. Required ordered sections (FR-012..024):

1. **Pitch** — who it's for + why, before any tech/architecture (FR-013).
2. **Platforms & status** — macOS Apple Silicon, Python 3.12; v1 status (FR-014).
3. **Install** — `git clone` → `uv sync` (FR-015, Principle VIII).
4. **Quickstart** — clone → first completed session report (FR-015; mirrors quickstart.md).
5. **Annotated report example** — generic; shows `asr:` provenance block, ≥1 grammar
   pattern, the `top_priority` line (FR-016, FR-017).
6. **Where things live** — reports in `data/sessions/`; questions in
   `content/questions.yaml`; override at `~/.speakloop/qa.yaml` (FR-018, FR-003).
7. **Contributor links** — constitution + `specs/` (FR-019).
8. **Known limitations** — placed *before* troubleshooting (FR-021): v1; accented
   jargon can be misheard; LLM feedback can degrade to fluency-only; audio replay
   exists, full pronunciation feedback does not.
9. **Troubleshooting** — entries per E3 (FR-022, FR-023, FR-024).

**Constraints**: plain Markdown, renders without extensions (FR-012); ~5-min read
(FR-020).

## E3 — Troubleshooting entry

A unit of the troubleshooting section.

| Field | Type | Constraint |
|---|---|---|
| symptom | short heading | visually prominent / scannable (FR-022, FR-024.4) |
| cause | one line | exactly one line (FR-022) |
| fix | single short paragraph | a local fix OR explicit "known v1 limitation" (FR-022, FR-024) |

**Required entries** (FR-023, minimum set): model-download failure (resume + proxy);
LLM feedback degraded to fluency-only (names the `phase_c_error` field + cause meanings);
technical term misheard (biasing + how to add domain terms; v1 limitation); VAD version
conflict (why pinned + recover via pinned reinstall); macOS mic permission first run;
recording-loop hang at final attempt (interim abort workaround + known/deferred note).

## E4 — Path-portability audit

An automated check classifying tracked-file content as portable or machine-specific leak.

| Aspect | Value |
|---|---|
| Input | Tracked files from `git ls-files -z` (decodable text only). |
| Flagged patterns | `(/Users/|/home/)[A-Za-z0-9._-]+/`; `[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\` |
| Excluded (portable) | `~/…`; angle-bracket placeholders (`/Users/<name>/`, `C:\Users\<name>\`); the audit module's own source. |
| Output (pass) | empty offender list; test passes. |
| Output (fail) | non-empty list of `path:line` strings; test fails naming each (FR-008). |
| Determinism | files sorted; same tree → same result (FR-011). |
| Budget | < 2 s wall clock (FR-011, SC-G). |

**Self-test invariant**: a synthetic concrete-login line must produce a hit (guards
against a no-op gate, SC-B).

## E5 — Question-not-found error

| Field | Value |
|---|---|
| Trigger | No `--qa-file`, no readable `~/.speakloop/qa.yaml`, no readable `content/questions.yaml`. |
| Behavior | One English message naming both default + override locations; non-zero exit; no empty session, no crash (FR-006). |
| Style | Matches existing `QALoadError` "not found" message in `content/loader.py`. |

## E6 — License file

| Field | Value |
|---|---|
| Location | repo root `LICENSE` |
| Content | MIT (constitution Non-Negotiables; FR-025/SC-E) |
| Status | Already present; verified during this feature. |
