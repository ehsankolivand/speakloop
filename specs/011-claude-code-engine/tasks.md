# Tasks: Claude Code Analysis Engine

**Feature**: `011-claude-code-engine` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

**Scope note**: Small feature — 17 tasks. No setup phase (zero new dependencies; stdlib only).
All automated tests run against an **injected fake runner** — no test ever spawns the real `claude`
binary or consumes credit (Constitution: "Live model calls in tests are forbidden").

**Pinned CLI**: behaviors encoded as named constants cite observed `claude 2.1.170` (research.md).

---

## Phase 1: Foundational (blocking prerequisites)

- [X] T001 [P] Create `src/speakloop/llm/claude_code_engine.py` scaffolding: the `LLMEngineError`
  subclasses (`ClaudeCodeNotInstalledError`, `ClaudeCodeAuthError`, `ClaudeCodeRateLimitError`,
  `ClaudeCodeTimeoutError`, `ClaudeCodeBadOutputError`), the `ClaudeCliResult` dataclass
  (`stdout`/`stderr`/`returncode`), pinned named constants for flags + envelope fields + stripped
  env-var names (each with a `# observed claude 2.1.170` comment), `build_env()` (copy of
  `os.environ` minus `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_BASE_URL`/
  `ANTHROPIC_API_URL`/`CLAUDE_CODE_USE_BEDROCK`/`CLAUDE_CODE_USE_VERTEX`), and `default_runner()` —
  the ONLY `subprocess` spawn of `claude` (timeout, user prompt on stdin, env from `build_env()`).
  Import `subprocess` function-locally so `--help` stays model-free.
- [X] T002 [P] Add a fake-CLI runner harness in `tests/helpers/fake_claude.py`: a factory returning
  a fake `runner` callable (records the argv + env it was given, returns a canned `ClaudeCliResult`),
  plus convenience builders for a success envelope, an `is_error` auth/rate envelope, a non-JSON
  blob, and a `FileNotFoundError`/`TimeoutExpired`-raising runner.

---

## Phase 2: User Story 1 — Subscription-billed analysis via Claude Code (P1) 🎯 MVP

**Goal**: `--engine claude` (or config default) routes every analysis call through the local Claude
Code, subscription-billed, with identical reports and graceful `analysis_pending` degradation.

**Independent test**: With a fake runner, a stubbed session produces a complete report through the
claude engine; with a failing fake runner the session degrades to `analysis_pending`; `doctor` shows
the Claude Code rows. (Live equivalent verified in T017.)

- [X] T003 [US1] Implement `ClaudeCodeEngine` in `src/speakloop/llm/claude_code_engine.py`:
  `__init__(*, model, runner=default_runner, timeout=90.0, binary="claude")` and
  `generate(system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False) -> str` —
  builds argv (`--print --output-format json --model <model> --safe-mode --tools "" \
  --no-session-persistence --system-prompt <system_prompt>`), invokes `runner`, parses the envelope
  (key off `is_error`, return `.result` stripped), maps failures to the taxonomy, `retry=True`
  appends a STRICT-JSON reminder to the user prompt (system prompt verbatim), ignores
  `max_tokens`/`temperature` (documented in docstring).
- [ ] T004 [P] [US1] Extend `LoopConfig` in `src/speakloop/config/loop_config.py` with additive
  optional keys `engine` (default `"local"`), `claude_fast_model` (`"haiku"`),
  `claude_strong_model` (`"sonnet"`) + tolerant parsing (invalid → default).
- [ ] T005 [US1] Add an engine-selection resolver in `src/speakloop/cli/practice.py`
  (`resolve_engine_choice(engine_flag, cloud_flag) -> str`): precedence explicit flag → `loop.yaml`
  `engine` → `"local"`; `--cloud` ⇒ `openrouter`; conflicting `--engine local|claude` + `--cloud`
  ⇒ clear error; unknown value ⇒ error listing valid choices.
- [ ] T006 [US1] In `src/speakloop/cli/practice.py`: add `_build_claude_grammar_analyzer(console)`
  mirroring `_build_cloud_grammar_analyzer` (build the claude engine, reuse the cloud grammar +
  coach prompt files, print the privacy disclosure + a `shutil.which` heads-up if absent/logged-out,
  return `(grammar_runner, coach_runner)` with `.runners` attached, **always non-None**); add an
  optional `fast_engine=None` kwarg to `_build_runners` (defaults to `engine` → byte-identical for
  local/openrouter); branch `run()` engine selection on the resolved choice (local/openrouter/claude).
- [ ] T007 [US1] In `src/speakloop/cli/main.py`: add `--engine` option to `practice_cmd` and
  `resume_cmd` (keep `--cloud`); thread the resolved engine into `_practice.run(...)` and
  `_resume.run(...)`.
- [ ] T008 [US1] In `src/speakloop/cli/resume.py`: replace the `if cloud` branch with the resolved
  engine selection (local/openrouter/claude), reusing the practice builders.
- [ ] T009 [US1] In `src/speakloop/cli/doctor.py`: add a `_claude_code()` section returning rows for
  binary presence (`shutil.which`), version (`claude --version`), auth state
  (`claude auth status --json` → `loggedIn`/`authMethod`/`subscriptionType`), the configured default
  engine (`loop_config.load().engine`), and an informational WARN if `ANTHROPIC_API_KEY` is in the
  ambient env; rows never FAIL the exit code; probe helpers monkeypatchable. Register in `_collect()`.
- [X] T010 [P] [US1] Parametrize the contract suite in `tests/contract/test_llm_interface.py` over
  `ClaudeCodeEngine(runner=fake_success)` — `generate("sys","user")` returns the canned string; keep
  the existing `StubLLMEngine` case green.
- [X] T011 [P] [US1] Unit tests in `tests/unit/test_claude_code_engine.py`: table-driven over every
  taxonomy branch (not_installed / not_authenticated / rate_limited / timeout / bad_output incl.
  unknown-flag stderr), `retry=True` user-prompt nudge with system prompt unchanged, `max_tokens`/
  `temperature` ignored, success returns `.result`, fenced output passes through, and an assertion
  that the env handed to the runner **never contains `ANTHROPIC_API_KEY`** even when `os.environ` does.
- [ ] T012 [P] [US1] Unit tests in `tests/unit/test_engine_selection.py` for the full precedence
  matrix (flag wins over config wins over default; `--cloud` alias; conflict error; unknown error).
- [ ] T013 [P] [US1] Integration tests: `tests/integration/test_claude_engine_degradation.py` (a
  stubbed coordinator/run with a failing claude engine proves `analysis_pending` is set, recordings
  + deterministic report preserved, resumable) and `tests/integration/test_doctor_claude_rows.py`
  (monkeypatched probe → expected Claude Code rows, never FAIL).
- [ ] T014 [US1] Update `src/speakloop/llm/CLAUDE.md` to document `claude_code_engine.py` as the
  third engine (the only `subprocess` claude spawn; `--safe-mode` not `--bare`; env-stripping;
  taxonomy; key off `is_error`).

**Checkpoint**: P1 is a complete MVP — claude engine works end-to-end (single model), degrades
gracefully, doctor reports it, suite green.

---

## Phase 3: User Story 2 — Per-call model tiering (P2)

**Goal**: cheap calls (mishearing, drills) use the fast model; reasoning-heavy calls use the strong
model; both overridable in `loop.yaml`.

**Independent test**: with a fake runner that records the `--model` argv, mishearing/drill calls use
`claude_fast_model` and coverage/consistency/follow-up/grammar/coach use `claude_strong_model`;
overriding the config changes the models used.

- [ ] T015 [US2] In `src/speakloop/cli/practice.py`: build two `ClaudeCodeEngine` instances
  (fast = `claude_fast_model`, strong = `claude_strong_model`) in `_build_claude_grammar_analyzer`,
  pass the fast one as `_build_runners(strong, fast_engine=fast)` so mishearing+drill → fast and the
  rest → strong; grammar + coach use strong. Define the call-site→tier mapping as a documented
  constant.
- [ ] T016 [P] [US2] Tests in `tests/unit/test_claude_tiering.py`: assert the per-call `--model`
  argv matches the expected tier for each runner, and that `loop.yaml` overrides change them.

---

## Phase 4: Polish & Live Verification

- [ ] T017 Run the full suite (`uv run pytest`) green, confirm `speakloop --help` stays model-free
  and the path-portability audit passes, run `ruff` on the new files; then perform the **live
  verification (overnight Step 2)** with the REAL CLI (≤15 calls, prefer `--model haiku` for probes):
  seed an `analysis_pending` session from fixtures and run `speakloop resume --engine claude`; confirm
  the JSON recovery ladder parses, the report is complete and well-formed, `ANTHROPIC_API_KEY` is
  absent from the subprocess environment, and a bogus binary path maps to graceful
  `analysis_pending`; record observed `claude --version` and per-call latencies into MORNING_REPORT.md.

---

## Dependencies & parallelism

- **Foundational (T001–T002)** blocks everything. T001 and T002 are different files → `[P]`.
- **US1 (T003–T014)**: T003 needs T001; T005–T008 need T003+T004; T009 is independent of the engine
  internals (uses its own probe); the test tasks T010–T013 are `[P]` once their targets exist.
- **US2 (T015–T016)** needs US1 (esp. T006's `fast_engine` kwarg).
- **T017** is last (needs the whole feature).

## Implementation strategy

- **MVP = Phase 2 (US1)** with a single claude model — fully usable and shippable on its own.
- **P2 (tiering)** is a pure refinement layered on the `fast_engine` seam; no rework of US1.
- Keep the suite green after each phase; commit + push per phase.
