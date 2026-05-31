---

description: "Tasks for 007-robust-model-download — port `download_aria.sh` into `src/speakloop/installer/` with parallel byte-range streams, indefinite resume, sleep prevention, optional credential, and the missing-aria2 fallback."

---

# Tasks: Resilient Model Downloads on Slow / Unstable Networks

**Input**: Design documents from `/specs/007-robust-model-download/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Test tasks are INCLUDED. The constitution's Development Guidelines and the existing `tests/` tree make test coverage the default expectation for this module; the three contracts in `contracts/` each pin specific test assertions, and the live `live_download` opt-in marker mirrors the established `live_asr` / `live_llm` pattern.

**Organization**: Tasks are grouped by user story (US1 = resilience, US2 = throughput, US3 = optional credential) from `spec.md`. Each user story is independently testable per `spec.md §User Scenarios & Testing`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3) — applies only to Phase 3+
- Include exact file paths in every description

## Path Conventions

Single-project layout (matches the existing speakloop repo). All implementation lives under `src/speakloop/installer/`; all unit tests under `tests/unit/installer/`; integration tests under `tests/integration/`; live opt-in tests at the `tests/` root (mirrors `tests/asr_pipeline_test.py` etc.); research lives at `doc/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pre-implementation housekeeping that does not depend on any code in the new module.

- [X] T001 [P] Drop `"hf-transfer>=0.1.9"` from the `dependencies` list in `pyproject.toml` (research §Decision 9; the dep is declared but never activated, and the chosen mechanism is aria2)
- [X] T002 [P] Add `live_download: opt-in real-network smoke test for the aria2 downloader; mirrors live_asr / live_llm; excluded from the default suite` to `[tool.pytest.ini_options].markers` in `pyproject.toml`
- [X] T003 [P] Create directory `tests/unit/installer/fixtures/aria2_output/` and populate it with the 7 captured stdout transcripts named in `contracts/progress-bridge-contract.md §5` (`normal_run.txt`, `resume_run.txt`, `transient_drop.txt`, `hard_auth.txt`, `hard_404.txt`, `disk_full.txt`, `missing_eta.txt`) — capture via real aria2 runs against a small public artifact, then sanitize any tokens
- [X] T004 [P] Create `doc/research_install.md` summarising the install-mechanism decision per Constitution Principle X: link to `specs/007-robust-model-download/research.md`, list the 9 decisions in 1-line form, name `download_aria.sh` as the source of the validated configuration

**Checkpoint**: Setup complete — repo is ready for the new module structure; no Python source has been edited yet, so the full test suite still passes against `main`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types and module-doc surface that every user story phase reads. NO user story tasks may begin until this phase is complete.

- [X] T005 Add four typed exceptions (`DownloadAuthError`, `DownloadNotFoundError`, `DownloadDiskError`, `ShardDiscoveryError`), all subclassing `InstallFailedError`, to `src/speakloop/installer/__init__.py` per `data-model.md §Exceptions added`; export them from `__all__`
- [X] T006 [P] Update `src/speakloop/installer/CLAUDE.md` (Purpose, Public interface, Dependencies, File map sections) to reflect the new module shape: list `aria.py`, `tokens.py`, `shards.py` alongside the existing files; remove the `huggingface_hub.snapshot_download` line from File map and replace with the dual-path description; keep the existing Traps section but mark Trap #1 (`resume_download=True`) as superseded by aria2's `--continue=true`

**Checkpoint**: Foundation ready — exception hierarchy is callable from any user story phase; module documentation reflects the design so subsequent edits stay coherent.

---

## Phase 3: User Story 1 — Hands-free completion on unreliable connection (Priority: P1) 🎯 MVP

**Goal**: A first-time user on a flaky home connection runs the install and walks away; on every dropped connection the download pauses, waits, and resumes from the prior byte offset; the Mac does not sleep; the install eventually completes without the user re-running anything. Fallback to `snapshot_download` if `aria2c` is not on `PATH`.

**Independent Test**: Per `spec.md §User Story 1 → Independent Test`: start a multi-gigabyte download on a constrained link, repeatedly cut and restore the network, leave the lid closed for a sustained interval; confirm the download finishes without any manual restart, the final byte count matches expected, and validation passes.

### Tests for User Story 1 (write first)

> **NOTE**: These tests MUST fail against `main` (the new modules / behavior do not exist yet). Write them first, watch them fail, then implement.

- [X] T007 [P] [US1] Unit test `tests/unit/installer/test_shards.py` covering: (a) repo with `model.safetensors.index.json` → returns `sorted(set(weight_map.values()))`; (b) repo without index file → returns `["model.safetensors"]`; (c) malformed index → raises `ShardDiscoveryError`; (d) index where `weight_map` is empty → raises `ShardDiscoveryError`
- [X] T008 [P] [US1] Unit test `tests/unit/installer/test_aria.py` driving each fixture from T003 through `_parse_progress(...)` and `_classify_exit(...)` and asserting the expected `Aria2Progress` / `Aria2Outcome` per `data-model.md §Aria2Outcome` and `contracts/progress-bridge-contract.md §2`
- [X] T009 [P] [US1] Replace `tests/unit/installer/test_downloader.py`: assert (a) `caffeinate -dimsu -w <os.getpid()>` is spawned at `download_model` entry; (b) when `shutil.which("aria2c")` is mocked to a path, the per-shard `aria2c` invocation contains all 8 pinned constants from `contracts/downloader-cli-contract.md §8`; (c) when `shutil.which("aria2c")` is mocked to `None`, `huggingface_hub.snapshot_download(resume_download=True, token=...)` is called instead and exactly one yellow warning line names `brew install aria2`; (d) a `TRANSIENT_FAILURE` outcome triggers a respawn after a 10 s sleep; (e) a `HARD_FAILURE` outcome raises the typed exception, no respawn
- [X] T010 [P] [US1] Integration test `tests/integration/test_aria_fallback.py` exercising the full `installer.ensure_models("A")` flow with `shutil.which` patched to return `None`: assert the consent prompt is still asked, `snapshot_download` is called via the injected `download_fn` seam, the yellow warning appears in captured console output, and validation gates readiness identically
- [X] T011 [P] [US1] Integration test `tests/integration/test_caffeinate_lifecycle.py`: assert (a) caffeinate is spawned BEFORE the consent prompt; (b) on a successful run, caffeinate is `terminate()`d in `finally`; (c) on `InstallDeclinedError`, caffeinate is also terminated; (d) on any unhandled exception, caffeinate is terminated. Use `subprocess.Popen` mock and `psutil`-free PID inspection — no real caffeinate spawn

### Implementation for User Story 1

- [X] T012 [P] [US1] Create `src/speakloop/installer/shards.py` exposing `discover_shards(local_dir: Path) -> list[str]` per `contracts/downloader-cli-contract.md §4`: pure function, raises `ShardDiscoveryError` on a malformed `model.safetensors.index.json`, returns `["model.safetensors"]` when no index file is present; no imports beyond `json`, `pathlib` and `speakloop.installer` (for the exception)
- [X] T013 [P] [US1] Create `src/speakloop/installer/aria.py` per `contracts/progress-bridge-contract.md §1-§3` and `data-model.md §Aria2Progress / §Aria2Outcome`: define `Aria2Progress` and `Aria2Outcome`, `_PROGRESS_RE` regex, `_parse_size(s) -> int`, `_parse_eta(s) -> int | None`, `_parse_progress(line, shard_filename) -> Aria2Progress | None`, `_classify_exit(exit_code: int, tail_lines: list[str]) -> tuple[Aria2Outcome, Exception | None]`, and `run(cmd: list[str], *, shard_filename: str, on_progress: Callable[[Aria2Progress], None]) -> tuple[Aria2Outcome, Exception | None]`. Use only stdlib (`subprocess`, `re`, `enum`, `dataclasses`)
- [X] T014 [US1] Rewrite `src/speakloop/installer/downloader.py:download_model(model, *, console=None)` to orchestrate per `contracts/downloader-cli-contract.md §1-§7`: (a) detect aria2 via `shutil.which`; (b) spawn `caffeinate -dimsu -w <pid>` in a try/finally; (c) aria2 path → metadata pass via `subprocess.run(["curl", ...])` for each name in `META_FILES` (FR-006 / FR-013 / contract §3), then `discover_shards`, then a `for shard in shards: while True: aria.run(...)` outer loop with the 10 s sleep on `TRANSIENT_FAILURE` and raise on `HARD_FAILURE`; (d) fallback path → emit yellow warning, call `snapshot_download(..., resume_download=True, token=...)`. Keep the public signature `download_model(model, *, console=None)` unchanged so `installer/__init__.py` and all existing tests still work. Token is `None` for now — US3 wires it in
- [X] T015 [US1] In `download_model`, build and drive a single `rich.progress.Progress` instance per `contracts/progress-bridge-contract.md §3`: one task per shard via `progress.add_task(description=f"{model.name} / {shard}", total=None)`; in the `on_progress` callback, `progress.update(task_id, total=snapshot.bytes_total, completed=snapshot.bytes_received)`; between aria2 respawns, call `progress.console.print("[yellow]Connection lost — retrying in 10s…[/yellow]")` and do NOT remove or reset the task — so completed bytes carry forward and the bar resumes from the prior offset (FR-020)

**Checkpoint**: User Story 1 is fully functional. A multi-gigabyte download survives Wi-Fi drops, the laptop does not sleep, and the install completes without manual intervention. The fallback path works at parity with today on a machine without aria2. Run `uv run pytest tests/unit/installer/ tests/integration/test_aria_fallback.py tests/integration/test_caffeinate_lifecycle.py tests/integration/test_phase_a_install_flow.py` — all green.

---

## Phase 4: User Story 2 — Substantial throughput on a constrained link (Priority: P2)

**Goal**: A user on a throttled link sees a multi-gigabyte model download finish in meaningfully less wall-clock time. The mechanism delivering this win (aria2's 16-stream byte-range split) already lights up in US1's invocation; US2 adds the live evidence path and the user-facing documentation that names the prereq.

**Independent Test**: Per `spec.md §User Story 2 → Independent Test`: on a controlled shaped link, time the same model with the new mechanism vs. the snapshot_download fallback (toggle by renaming `aria2c`); confirm the new mechanism's wall-clock time is at least 2× lower (research §Decision 8 SC-001 threshold).

### Tests for User Story 2

- [X] T016 [P] [US2] Create `tests/live_download_test.py` marked `pytest.mark.live_download` per `contracts/progress-bridge-contract.md §7`: skips if `shutil.which("aria2c") is None`, downloads exactly one small public artifact via the real `downloader.download_model(...)` against a small public HF repo (e.g., `mlx-community/Kokoro-82M-bf16` `config.json`), asserts the byte count matches HTTP `Content-Length`. Excluded from the default suite by the `live_download` marker (T002)

### Implementation for User Story 2

- [X] T017 [US2] Add a single line `brew install aria2` to the prerequisites section of `README.md`, immediately after the existing `uv` line and BEFORE the first `uv run speakloop` invocation; phrase it as "Recommended for faster, more resilient downloads on slow links — without it, speakloop falls back to a single-connection download." (matches Constitution Principle VIII's "guide the user" intent and surfaces FR-019)

**Checkpoint**: User Story 2 is demonstrable. The optional `uv run pytest -m live_download` confirms the real aria2 path works end-to-end; the manual A/B procedure in `quickstart.md §Throughput A/B` produces the SC-001 ≥ 2× evidence on a shaped link.

---

## Phase 5: User Story 3 — Anonymous-by-default, optional credential (Priority: P3)

**Goal**: A user with no credentials configured downloads all default public models successfully; a user who has run `huggingface-cli login` or who exports `$HF_TOKEN` gets their credential consumed at runtime for the model fetch only. No real or placeholder token is committed.

**Independent Test**: Per `spec.md §User Story 3 → Independent Test`: with no credentials configured, run the download and confirm all default models complete; separately, set `$HF_TOKEN` and confirm it is consumed by the downloader; grep the repo for credential-looking values and confirm none.

### Tests for User Story 3

- [X] T018 [P] [US3] Unit test `tests/unit/installer/test_tokens.py` covering the resolution table in `contracts/token-resolution-contract.md §2` and all 5 negative tests in §6 (env-empty-and-no-file → anonymous; env-set-with-file → env wins; file-with-trailing-newline → stripped; whitespace-only-file → anonymous; `repr(ResolvedToken)` redacts the value)
- [X] T019 [P] [US3] Integration test `tests/integration/test_anonymous_download.py`: with `monkeypatch.delenv("HF_TOKEN", raising=False)` and `~/.cache/huggingface/token` patched-absent, run the download path with `shutil.which("aria2c")` mocked to a sentinel; assert the constructed curl and aria2c invocations DO NOT contain any `Authorization` header / `--header=Authorization` flag, and the diagnostic `Using HuggingFace token from …` line is NOT printed
- [X] T020 [P] [US3] Extend `tests/integration/test_path_portability_audit.py` to also assert FR-013 / SC-006: no committed file outside `doc/` and `specs/` contains a string matching `r"\bhf_[A-Za-z0-9]{20,}\b"` (the HF token format); add a fixture-driven negative assertion so the test itself fails if anyone commits a literal token

### Implementation for User Story 3

- [X] T021 [P] [US3] Create `src/speakloop/installer/tokens.py` exposing `ResolvedToken` (frozen dataclass with `__repr__` redaction per `contracts/token-resolution-contract.md §3`) and `resolve_token() -> ResolvedToken` implementing the env → file → anonymous precedence per §1-§2: pure function, no logging, no exceptions on missing inputs, strips trailing whitespace from the file contents
- [X] T022 [US3] In `src/speakloop/installer/downloader.py`: at the top of `download_model`, call `token = resolve_token()`; print the diagnostic line per `contracts/token-resolution-contract.md §5` (only for `env` / `hf_cli_file` sources, never for `anonymous`); thread `token.value` through (a) the curl invocations as `-H "Authorization: Bearer ..."` only when non-None, (b) the aria2c invocations as `--header=Authorization: Bearer ...` only when non-None, (c) the `snapshot_download(token=token.value)` fallback kwarg

**Checkpoint**: User Story 3 is fully functional. `unset HF_TOKEN && rm -f ~/.cache/huggingface/token && uv run speakloop doctor && (run install)` succeeds against public models. `export HF_TOKEN=hf_xxxxx && (run install against a private mirror)` consumes the token. `rg "hf_[A-Za-z0-9]{20,}" -- ':!doc' ':!specs'` finds nothing.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, the `doctor` integration named in the plan, the final manual validation suite, and the SC-001 evidence capture. Touches multiple files across the repo.

- [X] T023 [P] Update `src/speakloop/installer/CLAUDE.md` Traps section with one new entry: "Don't add a second parallel-download backend. `hf-transfer` was removed in feature 007 because the chosen mechanism (aria2c) already covers parallel byte-range streams AND indefinite retry AND sleep prevention; a second backend would re-fragment the path."
- [X] T024 [P] Re-check the top-level `CLAUDE.md` SPECKIT block written during `/speckit-plan` against what actually shipped; correct any wording where scope drifted during implementation
- [X] T025 Extend the `speakloop doctor` command to detect `aria2c` on `PATH` and report it under a new "Install accelerator" row: `OK` when present (with version from `aria2c --version | head -1`), `WARN: install with 'brew install aria2' for faster, more resilient downloads` when absent. Locate the doctor implementation via `rg -n "def doctor" src/speakloop/cli/` and update accordingly; mirror the row style used by the existing model-health rows
- [X] T026 Run `uv run pytest` and confirm the entire default suite is green; fix any regressions introduced by the rewrite of `downloader.py` (callers go through `installer.ensure_models(...)`, whose signature has not changed, so regressions should be confined to `tests/unit/installer/`)
- [ ] T027 [P] Run `uv run pytest -m live_download` once on the dev machine; record the outcome (pass / skip-reason) in the PR description — **deferred** (live test requires real network; user instruction excluded it from this run)
- [ ] T028 Walk through the four resilience / fallback scenarios documented in `quickstart.md §Resilience verification`; record outcomes in the PR description (Wi-Fi drops survived; lid-close survived; missing-aria2 fallback printed warning + completed; anonymous-only install succeeded) — **deferred** (real-hardware validation, post-merge per plan)
- [ ] T029 Capture SC-001 evidence per `quickstart.md §Throughput A/B`: time Qwen3-14B-4bit once via fallback (rename aria2c), once via aria2; record the ratio in the PR description. Acceptance bar from research §Decision 8 is ≥ 2× speedup — **deferred** (real-hardware validation, post-merge per checklist Q4)
- [X] T030 [P] Run `uv run ruff check src/speakloop/installer/` over the new and modified files; fix any new findings (do NOT silently widen the existing repo-level lint exclusions)

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no internal dependencies; T001-T004 can all run in parallel.
- **Phase 2 (Foundational)**: depends only on Phase 1 (T002 marker is referenced by T016's marker decorator, T005 exception types are imported by T012/T013/T014).
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on Phase 3 (the live test invokes the implementation from US1).
- **Phase 5 (US3)**: depends on Phase 3 (the token threading patches the orchestrator created in US1).
- **Phase 6 (Polish)**: depends on Phases 3, 4, 5.

### User story dependencies (per spec.md priorities)

- **US1 (P1)** is the MVP slice. After US1 ships, resilience + fallback are fully functional; throughput is implicitly delivered because aria2c's default invocation IS multi-stream; auth is anonymous-only.
- **US2 (P2)** depends on US1 because the aria2c code path it exercises was created in US1. It adds the live test marker and the README prereq line.
- **US3 (P3)** depends on US1 because it patches `download_model` (created in US1) with token threading. It is otherwise independent of US2.

### Within each story

- Tests are written first and watched to fail (T007-T011, T016, T018-T020).
- Then implementation (T012-T015, T017, T021-T022).
- Tests are re-run and required to pass before the phase Checkpoint.

### Parallel opportunities

- All Phase 1 tasks marked `[P]` can run in parallel (4 independent files).
- T006 ([P] in Phase 2) is independent of T005 (different files).
- Within US1, the test tasks T007-T011 are all `[P]` (5 independent test files); the implementation tasks T012 and T013 are `[P]` (independent files); T014 / T015 are sequential and touch `downloader.py`.
- Within US3, T018-T020 are `[P]` (3 independent test files), T021 is `[P]` (new file), T022 is sequential (it edits `downloader.py` which is owned by US1's T014 — must run AFTER T014 lands).
- Phase 6 polish tasks T023, T024, T027, T030 are `[P]`; T025, T026, T028, T029 are sequential (they read code state or capture evidence that depends on prior tasks).

---

## Parallel Example: User Story 1

```bash
# Step 1: write all five US1 test files in parallel (each fails initially)
Task: "Unit test tests/unit/installer/test_shards.py"
Task: "Unit test tests/unit/installer/test_aria.py"
Task: "Unit test tests/unit/installer/test_downloader.py (replace)"
Task: "Integration test tests/integration/test_aria_fallback.py"
Task: "Integration test tests/integration/test_caffeinate_lifecycle.py"

# Step 2: implement the two leaf modules in parallel
Task: "Create src/speakloop/installer/shards.py"
Task: "Create src/speakloop/installer/aria.py"

# Step 3: implement the orchestrator (sequential — both edit downloader.py)
Task: "Rewrite src/speakloop/installer/downloader.py:download_model"
Task: "Wire rich.progress.Progress inside downloader.py"
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (US1). At this checkpoint:
   - Multi-gigabyte downloads survive Wi-Fi drops on a flaky link.
   - The Mac stays awake.
   - Missing-`aria2c` fallback degrades gracefully to today's behavior.
   - The Rich progress display matches FR-020.
3. STOP and validate: walk through `quickstart.md §Resilience verification` scenarios 1-3 against a real download.
4. Ship the MVP if no regressions in the default `uv run pytest` suite.

### Incremental delivery

- After US1 (MVP) ships: optionally fold in US2 and US3 in the same PR (they are small) or as follow-up PRs:
  - US2 adds the `live_download` opt-in test and the README prereq line — both are documentation and one new test file; no behavior change.
  - US3 adds optional auth — a new `tokens.py` and one edit to `downloader.py`; users without a token are unaffected.
- Phase 6 polish lands in the same PR as whichever phase is last shipped.

### Why this map preserves the spec's user-story priorities

Although the chosen mechanism delivers all three user-story benefits in one structural change (aria2 + caffeinate + token-aware headers), the task map keeps them as separable phases so:

- A team that only completes Phase 3 still ships a real, demonstrable resilience win (US1's `Independent Test` passes).
- Phase 4 can land later without code coupling to Phase 5.
- Phase 5 is the smallest, last, most-additive slice — matching its P3 priority in the spec.

---

## Notes

- All tasks reference exact file paths and contract sections so an implementer (or an LLM) can act on each without re-reading the conversation.
- The public `installer.ensure_models(...)` signature is preserved by the plan (`plan.md §Project Structure`); existing tests at `tests/integration/test_phase_a_install_flow.py` are NOT modified — they inject `download_fn` and remain a regression guard for the orchestrator's contract.
- The eight pinned constants in `contracts/downloader-cli-contract.md §8` are the source of truth for the aria2 flag values; changing any of them in implementation requires updating the contract AND the test assertions in T009 / T013 in the same commit.
- This feature does NOT modify the report pipeline (`feedback/` and `debrief/`), the engine wrappers (`asr/`, `llm/`, `tts/`), the consent prompt (`installer/consent.py`), the manifest (`installer/manifest.py`), or the validator (`installer/validator.py`). Any task that proposes such an edit is out of scope.
