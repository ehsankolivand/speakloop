---
description: "Task list for OpenRouter Cloud-Model Provider"
---

# Tasks: OpenRouter Cloud-Model Provider

**Input**: Design documents from `/specs/008-openrouter-cloud-provider/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — plan.md enumerates a unit + integration suite and the
constitution mandates per-module tests (engine tests use cached fixtures / mocks;
live model calls are forbidden in the default suite — the one real OpenRouter
round-trip is opt-in behind the `live_cloud` marker).

**Organization**: Tasks are grouped by user story (US1–US5) so each story is
independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 (user-story phases only)
- All paths are repo-root-relative (single-project layout under `src/speakloop/`)

## Path Conventions

Single project: `src/speakloop/<module>/`, `tests/unit/<module>/`,
`tests/integration/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test-harness plumbing only — no runtime dependency changes (transport
is stdlib `urllib`; the model-id YAML uses `pyyaml`, already a dependency).

- [X] T001 [P] Register the `live_cloud` pytest marker in `pyproject.toml` under `[tool.pytest.ini_options].markers` (mirrors the existing `live_asr` / `live_download` markers), excluded from the default suite; confirm NO new runtime dependency is added.
- [X] T002 [P] Ensure test package dirs exist (create empty `__init__.py` only if missing): `tests/unit/llm/__init__.py`, `tests/unit/feedback/__init__.py`, `tests/unit/config/__init__.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared seams every cloud story builds on — the path accessors and the
additive analyzer parameter. These are byte-for-byte safe for the local path.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T003 [P] Add three pure path accessors to `src/speakloop/config/paths.py`: `openrouter_token_path()` → `~/.speakloop/openrouter_token`, `openrouter_prompt_path()` → `~/.speakloop/openrouter_prompt.txt`, `openrouter_config_path()` → `~/.speakloop/openrouter.yaml` (all anchored on `_speakloop_home()`; PATHS only — no file reads, keeping the config leaf stdlib-only per `config/CLAUDE.md`).
- [X] T004 [P] Extend `tests/unit/config/test_paths.py` to cover the three new accessors: correct defaults, `SPEAKLOOP_HOME` override honored, pure (no I/O at call time).
- [X] T005 Add an additive `system_prompt: str | None = None` keyword to `analyze(...)` in `src/speakloop/feedback/grammar_analyzer.py`, threading it into `_generate_and_parse(...)`; when `None`, use the module-local `_SYSTEM_PROMPT` so every existing/local caller is byte-for-byte unchanged.
- [X] T006 Extend `tests/unit/feedback/test_grammar_analyzer.py`: `analyze(..., system_prompt=X)` forwards `X` to `llm.generate` as the system prompt; the default path still passes `_SYSTEM_PROMPT`; all existing local cases stay green (depends on T005).

**Checkpoint**: Shared accessors + analyzer override ready — user stories can begin.

---

## Phase 3: User Story 1 - Run a practice session without the local language model (Priority: P1) 🎯 MVP

**Goal**: With a valid OpenRouter token already configured (env or stored file),
`speakloop practice --cloud` produces grammar/coherence feedback via an
OpenRouter model and never loads the local Qwen weights.

**Independent Test**: On an environment with the local Qwen model absent and
`OPENROUTER_API_KEY` set (engine mocked at the `urllib` boundary), run the cloud
branch and confirm a complete grammar report is produced and `QwenEngine` /
`QWEN3_14B_4BIT` validation is never touched.

### Implementation for User Story 1

- [X] T007 [P] [US1] Create `src/speakloop/llm/openrouter_engine.py`: `OpenRouterEngine` implementing the `LLMEngine` Protocol via stdlib `urllib.request` POST to `https://openrouter.ai/api/v1/chat/completions` (Bearer auth, OpenAI-compatible body, returns `choices[0].message.content` stripped); add `OpenRouterAuthError(LLMEngineError)`, a `check_auth()` preflight (`GET /key`), and the error mapping from `contracts/openrouter-engine-contract.md` (401/403→auth, 404→model-named error, 5xx/timeout→`LLMEngineError`, token never in any message). Stdlib-only imports; no network at import time.
- [X] T008 [P] [US1] Create `src/speakloop/llm/openrouter_credentials.py`: `resolve_token() -> str | None` (env `OPENROUTER_API_KEY` > `~/.speakloop/openrouter_token` > `None`, empty treated as unset) and `store_token(value) -> Path` (strip, refuse empty, write `0600`). No interactive I/O, no import-time I/O.
- [X] T009 [P] [US1] Create `src/speakloop/llm/openrouter_config.py`: `resolve_model() -> str` reads `paths.openrouter_config_path()` YAML `model:` via `pyyaml`, else default `qwen/qwen3.7-max`; missing/empty key or malformed YAML degrades to the default (never crashes).
- [X] T010 [P] [US1] Create the packaged default cloud prompt asset `src/speakloop/feedback/openrouter_prompt_default.txt` — its OWN English content (NOT copied from `grammar_analyzer._SYSTEM_PROMPT`), instructing the same strict `{"errors":[{"attempt_ordinal","quote","corrected","error_type","explanation"}]}` JSON the verify/rank pipeline consumes.
- [X] T011 [US1] Create `src/speakloop/feedback/cloud_prompt.py`: `load_cloud_prompt() -> tuple[str, Path]` — seed `paths.openrouter_prompt_path()` from the packaged default if absent, read it verbatim, return `(text, path)`; never reads the local `_SYSTEM_PROMPT` (depends on T003, T010).
- [X] T012 [US1] Add a `--cloud` boolean option to the `practice` command in `src/speakloop/cli/main.py` and plumb `cloud=cloud` into `practice.run(...)` (default `False`; help text per `contracts/cloud-analyzer-bridge-contract.md`).
- [X] T013 [US1] In `src/speakloop/cli/practice.py`, add `cloud: bool = False` to `run(...)` and implement `_build_cloud_grammar_analyzer(console)` (function-local imports): `resolve_token()` (if `None`, actionable error → `typer.Exit(1)` — interactive capture is added in US2), preflight `check_auth()`, `load_cloud_prompt()` (print the editable path once), build `OpenRouterEngine(model=resolve_model(), token=...)`, and return `lambda transcripts: analyze(transcripts, engine, system_prompt=cloud_prompt)`; the branch MUST NOT validate or instantiate the local Qwen model (depends on T005, T007, T008, T009, T011).

### Tests for User Story 1

- [X] T014 [P] [US1] Create `tests/unit/llm/test_openrouter_engine.py` (mock `urllib`): request URL/method/headers/body shape; `system` message equals the passed `system_prompt`; 200→content; 401→`OpenRouterAuthError`; 404→`LLMEngineError` naming the model; 5xx/timeout→`LLMEngineError`; token absent from every raised message; `check_auth()` maps 200/401/other; `retry=True` still posts valid JSON.
- [X] T015 [P] [US1] Create `tests/integration/test_cloud_mode.py`: with `OPENROUTER_API_KEY` set and the engine mocked at the `urllib` boundary, the `--cloud` branch yields a grammar report with the local Qwen model absent, and asserts `QwenEngine` / `QWEN3_14B_4BIT` validation is never invoked (SC-002).

**Checkpoint**: MVP — cloud feedback works end-to-end given a configured token.

---

## Phase 4: User Story 2 - One-time token capture, then silent reuse (Priority: P1)

**Goal**: First `--cloud` run with no token prompts exactly once (with the privacy
disclosure), stores it, and proceeds; later runs reuse it silently; a
missing/rejected token surfaces a clear, actionable error.

**Independent Test**: Delete any stored credential, run `--cloud` and supply a
token → completes and stores; run again → no prompt; supply/store an invalid token
→ actionable error naming both remediation paths.

### Implementation for User Story 2

- [X] T016 [US2] Extend `_build_cloud_grammar_analyzer(...)` in `src/speakloop/cli/practice.py`: when `resolve_token()` is `None`, print the one-time privacy disclosure (FR-018) then prompt once and `store_token()`; empty/declined → actionable error (how to set the token / run without `--cloud`) → `typer.Exit(1)`. On preflight `OpenRouterAuthError`, print an actionable error naming both remediation paths, re-prompt once, re-store, re-check; still bad → `Exit(1)`. Print a one-line cloud reminder (active model id + transcript disclosure) on entry (depends on T013).
- [X] T017 [P] [US2] Create `tests/unit/llm/test_openrouter_credentials.py`: env > file > None precedence; empty env treated as unset; `store_token` writes `0600` and round-trips via `resolve_token`; no import-time I/O; token value never logged.

### Tests for User Story 2

- [X] T018 [US2] Extend `tests/integration/test_cloud_mode.py`: first run (no token, mocked input) → exactly one prompt + disclosure shown + token stored; second run → zero prompts, silent reuse; preflight 401 → actionable error + single re-prompt; empty/declined → non-zero exit, no empty credential written (SC-003, SC-006) (depends on T016).

**Checkpoint**: Token lifecycle complete — capture once, reuse silently, fail clearly.

---

## Phase 5: User Story 3 - Local/offline experience unchanged for non-adopters (Priority: P1)

**Goal**: Without `--cloud`, behavior is byte-for-byte unchanged: local Qwen flow,
no token prompt, no network, identical report output.

**Independent Test**: Run default `practice` with no token and no network → behaves
exactly as before the feature, including report content; importing the CLI loads no
engine packages.

### Tests for User Story 3

- [X] T019 [P] [US3] Create `tests/integration/test_local_mode_unchanged.py`: default `practice` (no `--cloud`, no `OPENROUTER_API_KEY`, no stored token, no network) produces the same grammar/report output as the local path for fixed inputs (`schema_version` stays 1, no new frontmatter), issues no token prompt, and never constructs `OpenRouterEngine` (SC-001).
- [X] T020 [P] [US3] Extend `tests/integration/test_help_without_models.py`: with the new cloud modules present, importing `speakloop.cli.main` still loads none of the engine packages (`mlx_lm`/`mlx_whisper`/`silero_vad`/`parakeet_mlx`); `speakloop --help` lists `--cloud` and stays model-free (< 2 s).

**Checkpoint**: Default path provably unregressed and still offline.

---

## Phase 6: User Story 4 - Change the cloud model with one setting (Priority: P2)

**Goal**: Editing the single `model:` line in `~/.speakloop/openrouter.yaml` (no
code change) swaps the OpenRouter model on the next cloud run.

**Independent Test**: Set `model: <other>` in the YAML, run `--cloud` → the request
targets `<other>`; with the file/key absent → `qwen/qwen3.7-max`.

### Implementation for User Story 4

- [X] T021 [P] [US4] Create `tests/unit/llm/test_openrouter_config.py`: absent file → `qwen/qwen3.7-max`; `model: X` → `X` (stripped); present-but-missing/empty key → default; malformed YAML → default (no crash) (validates SC-004's resolver behavior).
- [X] T022 [US4] Add a "Cloud" section to `src/speakloop/cli/doctor.py` reporting the active OpenRouter model id (via `resolve_model()`), the config file path, and whether it exists — additive `CheckRow`s, no change to existing checks.
- [X] T023 [US4] Extend `tests/integration/test_cloud_mode.py`: writing `model: <other>` to `~/.speakloop/openrouter.yaml` makes the cloud build target `<other>` with no code change; absent file → default (SC-004) (depends on T013, T009).

**Checkpoint**: Model id is swappable via one YAML edit and visible in `doctor`.

---

## Phase 7: User Story 5 - Tune cloud behavior by editing a dedicated prompt file (Priority: P3)

**Goal**: Editing `~/.speakloop/openrouter_prompt.txt` (no code change) changes the
cloud model's behavior next run; the file is wholly separate from the local prompt.

**Independent Test**: Edit the seeded prompt file → next `--cloud` run sends the
edited system prompt; local mode output is unaffected.

### Implementation for User Story 5

- [X] T024 [P] [US5] Create `tests/unit/feedback/test_cloud_prompt.py`: missing user file → seeded from the packaged default then read; present (edited) file → read verbatim, not re-seeded/overwritten; the loader never imports or reads `grammar_analyzer._SYSTEM_PROMPT` (FR-012); returns the editable path.
- [X] T025 [US5] Extend the `doctor` "Cloud" section in `src/speakloop/cli/doctor.py` to also report the cloud prompt-file path (`openrouter_prompt_path()`), whether it exists, and whether a token is present (depends on T022).
- [X] T026 [US5] Extend `tests/integration/test_cloud_mode.py`: editing the seeded `~/.speakloop/openrouter_prompt.txt` changes the system prompt passed to the (mocked) engine on the next run; the local-mode system prompt is unaffected (SC-005) (depends on T011, T013).

**Checkpoint**: Cloud prompt is user-editable, separate from local, and verified.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Per-module `CLAUDE.md` updates (Principle IV — same-commit), research +
README docs, the opt-in live smoke, and a final green-suite verification.

- [X] T027 [P] Update `src/speakloop/llm/CLAUDE.md`: second engine; new files (`openrouter_engine.py`, `openrouter_credentials.py`, `openrouter_config.py`); traps (only file touching OpenRouter; stdlib `urllib`; offline/import-time guard; preflight vs graceful-degradation).
- [X] T028 [P] Update `src/speakloop/feedback/CLAUDE.md`: `cloud_prompt.py` loader + packaged `openrouter_prompt_default.txt`; the additive `analyze(system_prompt=...)` param; cloud prompt is separate from `_SYSTEM_PROMPT`.
- [X] T029 [P] Update `src/speakloop/config/CLAUDE.md`: three new path accessors; note the model-id YAML is read in `llm/` so the leaf stays stdlib-only.
- [X] T030 [P] Update `src/speakloop/cli/CLAUDE.md`: `--cloud` flag, `_build_cloud_grammar_analyzer`, doctor "Cloud" section.
- [X] T031 [P] Append a "Cloud provider option (008)" section to `doc/research_llm.md`: OpenRouter decision, default `qwen/qwen3.7-max`, stdlib-urllib transport, model-id YAML, and the Principle II/III opt-in trade-off (Principle X).
- [X] T032 [P] Add a "Cloud mode (optional)" section to `README.md` mirroring `quickstart.md` (token capture, `~/.speakloop/openrouter.yaml` model swap, prompt-file tuning, privacy note, stay-local default).
- [X] T033 [P] Add an opt-in live smoke `tests/live_cloud_test.py` (marker `live_cloud`): one real OpenRouter round-trip against a cheap model, skipped unless `OPENROUTER_API_KEY` is set and the marker is selected; excluded from the default suite.
- [X] T034 Final verification: run `uv run pytest` (default suite — no live markers), `uv run speakloop --help`, and `uv run speakloop doctor`; confirm all green, `--help`/`doctor` stay model-free, and fix any regression surfaced.

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → no dependencies; can run first, in parallel.
- **Foundational (T003–T006)** → blocks all user stories. T003∥T005 (different files); T004 after T003; T006 after T005.
- **US1 (T007–T015)** → depends on Foundational. T007∥T008∥T009∥T010 (new files); T011 after T003+T010; T013 after T005+T007+T008+T009+T011; T012 independent of T013 (different file) but both land the entry point; T014 after T007; T015 after T013.
- **US2 (T016–T018)** → depends on US1 (T013, T008). T017 ∥ (different file); T018 after T016.
- **US3 (T019–T020)** → depends on US1 landing the branch (so the "no branch taken" path is real) + Foundational; both [P] (different test files).
- **US4 (T021–T023)** → T021 ∥ (after T009); T022 after T009; T023 after T013+T009.
- **US5 (T024–T026)** → T024 ∥ (after T011); T025 after T022; T026 after T011+T013.
- **Polish (T027–T034)** → after the stories they document; T027–T033 are [P] (different files); T034 runs last.

**Story independence**: US1 is a standalone MVP. US2/US4/US5 each extend the US1
branch and are independently testable. US3 is a pure regression guard and can be
validated as soon as the US1 branch exists.

## Parallel Execution Examples

- **Setup**: T001, T002 together.
- **Foundational kickoff**: T003 and T005 together (different files); then T004 and T006.
- **US1 new files**: T007, T008, T009, T010 together (four new files, no shared edits), then T011 → T013, with T012 alongside.
- **US1 tests**: T014 in parallel with implementation once T007 exists; T015 after T013.
- **Polish docs**: T027, T028, T029, T030, T031, T032, T033 all in parallel (distinct files); T034 last.

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + Phase 3 (US1)**: cloud feedback works given a
  configured token, without loading local Qwen. Shippable on its own.
- **Increment 2 (US2)**: add first-run capture + silent reuse + disclosure + clear
  auth errors — completes the "usable without pre-setting an env var" experience.
- **Increment 3 (US3)**: lock in the unchanged-local guarantee with regression
  tests (can be done any time after the US1 branch exists).
- **Increment 4 (US4) / Increment 5 (US5)**: prove the model-id and prompt-file
  config surfaces are editable with no code change, and surface them in `doctor`.
- **Polish**: module `CLAUDE.md` + research + README (Principle IV/X), opt-in live
  smoke, final green-suite check.

## Notes

- `[P]` = different files, no incomplete dependency. Same-file edits (e.g., the two
  `practice.py` tasks T013/T016, or the two `doctor.py` tasks T022/T025) are
  intentionally sequential.
- Tests use cached fixtures / mocked `urllib` (no live calls in the default suite);
  the single real round-trip is opt-in behind `live_cloud` (constitution dev
  guideline).
- No new runtime dependency (stdlib `urllib`; `pyyaml` already present). The local
  Qwen flow and `ensure_models(...)` are untouched.
