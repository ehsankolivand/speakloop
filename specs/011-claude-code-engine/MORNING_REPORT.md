# Morning Report — 011 Claude Code Analysis Engine

**Date**: 2026-06-10 (overnight autonomous run)
**Branch**: `011-claude-code-engine` (pushed; **not** merged into `main`, per your instructions)
**Status**: ✅ Complete. Full spec-kit flow + implementation + live verification all done. Ready for your review.

---

## TL;DR

A third analysis engine — **`claude`** — now drives every LLM analysis call through your locally
installed, logged-in **Claude Code** (subscription-billed, zero marginal token cost). Select it with
`--engine claude` or set it once in `~/.speakloop/loop.yaml`. `--cloud` still works (now an alias for
`--engine openrouter`). The local Qwen default is byte-identical and offline. Zero new dependencies.

- **Suite**: `622 passed, 3 skipped, 2 deselected` (was `567 passed` at the start → **+55 tests**).
- **Live-verified 11/11** against the real CLI (`claude 2.1.170`), including subscription billing safety.
- **Adversarial review pass**: 5 review lenses + per-finding verification (13 agents) found **no real
  code defects** — only 2 low-severity test-coverage gaps, now filled. See "Adversarial review" below.
- **8 commits** pushed across the phases (spec → plan → tasks → engine → US1 → US2 → report → review).

---

## What was built

A new `LLMEngine` implementation that drives the Claude Code CLI in non-interactive print mode via
stdlib `subprocess` (no SDK). It sits behind the existing injected interface exactly like the Qwen and
OpenRouter engines — **zero call-site changes, zero prompt/schema changes, report `schema_version`
stays 1.**

| Area | Change |
|------|--------|
| `src/speakloop/llm/claude_code_engine.py` (NEW, 329 lines) | The only file that spawns `claude`. `ClaudeCodeEngine`, the error taxonomy, `build_env()` (billing-safety env strip), `default_runner`, `doctor_probe()`. CLI behaviors pinned as named constants citing observed `claude 2.1.170`. |
| `src/speakloop/config/loop_config.py` | Additive optional keys: `engine`, `claude_fast_model`, `claude_strong_model`. |
| `src/speakloop/cli/main.py` | `--engine local\|openrouter\|claude` on `practice` + `resume`; `--cloud` kept as an alias. |
| `src/speakloop/cli/practice.py` | `resolve_engine_choice()`, `_build_claude_grammar_analyzer()`, `_build_runners(..., fast_engine=)`, model-tier map. |
| `src/speakloop/cli/resume.py` | Engine-selection branch (local / openrouter / claude). |
| `src/speakloop/cli/doctor.py` | New "Claude Code" section: binary, version, auth state, default engine, ANTHROPIC_API_KEY-in-env warning. |
| `src/speakloop/llm/CLAUDE.md`, root `CLAUDE.md` | Documented the third engine; SPECKIT block promotes 011 to active. |
| Tests (6 files, 51 claude-engine tests) | Contract param, engine unit (taxonomy/retry/env/argv/doctor), selection precedence, tiering, degradation integration, doctor rows. All use an **injected fake runner** — no test spawns the real binary. |

How it works (pinned to `claude 2.1.170`):
```
claude --print --output-format json --model <alias> --safe-mode --tools "" \
       --no-session-persistence --system-prompt <system_prompt>      # user prompt on stdin
```
- Keys off the envelope's **`is_error`** field (NOT `subtype`, which stays `"success"` even on error);
  returns `.result` (markdown fences left for the existing `_extract_json` recovery ladder).
- Failures map to `LLMEngineError` subclasses (`ClaudeCodeNotInstalledError` / `…AuthError` /
  `…RateLimitError` / `…TimeoutError` / `…BadOutputError`) → the coordinator's existing
  `analysis_pending` degradation fires unchanged. No auto-fallback to local (matches OpenRouter).
- **Billing safety**: the subprocess env is a copy of `os.environ` with `ANTHROPIC_API_KEY` +
  related override vars removed, so calls always bill to your subscription.

---

## Live verification (overnight Step 2) — real CLI, 11/11 PASS

Exercised the **real** Claude Code engine end-to-end (script: `/tmp/verify_claude_engine.py`, not
committed). Seeded an `analysis_pending` session from fixtures and ran `resume --engine claude`:

```
[PASS] seeded analysis_pending session
[PASS] resume --engine claude completed — wall-clock 67.4s
[PASS] analysis_pending cleared
[PASS] generated_by_phase advanced to C
[PASS] report well-formed (frontmatter parses + body present) — 5396 bytes
[PASS] grammar analysis ran (JSON parsed via recovery ladder) — 2 patterns found
[PASS] answer_grade assigned — grade=fair
[PASS] coverage scored through the real engine (strong tier) — 3 attempt coverage records
[PASS] ≥1 real Claude Code call made — 2 calls
[PASS] ANTHROPIC_API_KEY stripped from every subprocess env — env_has_api_key=False on all calls
[PASS] bogus binary → graceful ClaudeCodeNotInstalledError
11/11 checks passed
```

- **JSON parsed through the recovery ladder**: ✅ grammar (2 patterns) + coverage (3 records).
- **Report complete & well-formed**: ✅ rewritten, `analysis_pending` cleared, phase → C, grade recomputed.
- **`ANTHROPIC_API_KEY` absent from the subprocess env**: ✅ — I set a *bogus* `ANTHROPIC_API_KEY` in
  the environment before the run; the engine stripped it on **every** real call (`env_has_api_key=False`),
  so billing stayed on the subscription (returncode 0).
- **Graceful error mapping**: ✅ a bogus binary path (`/nonexistent/path/claude`) mapped to
  `ClaudeCodeNotInstalledError` (an `LLMEngineError`) → degradation path, no crash.

### Observed CLI version & per-call latencies
- `claude --version` → **`2.1.170 (Claude Code)`** (path `/Users/<you>/.local/bin/claude`).
- Real per-call latencies (this is the genuine cost of a real reasoning call, incl. Claude Code
  startup + model + thinking):
  - **grammar** (strong tier, `sonnet`): **~42–60 s** per call (varied across runs: 41.8s, 44.1s, 60.0s).
  - **coverage** (strong tier, `sonnet`): **~7.3 s**.
  - **trivial probe** (fast tier, `haiku`): **~2.9 s** (the Phase-0 envelope probe).
- **Real billed calls used overnight: ~5** (well under your 15-call cap). Auth/version probes and the
  `--bare` auth-failure probe were free / `$0`.

> ⚠️ **Observation (not a bug)**: the grammar call on `sonnet` is the slowest step (up to ~60 s with
> only 3 short attempts). A full live `practice` session runs ~8 analysis calls; the post-session
> analysis could take a few minutes. The hard per-call timeout is **90 s** (spec default) — headroom
> over the observed 60 s, but a very long answer could approach it. The timeout is a
> `ClaudeCodeEngine(timeout=...)` constructor arg (currently fixed at 90 s, not yet exposed in
> `loop.yaml`). See "Open items".

---

## How to use it (for you)

**Set Claude Code as your default engine (one line):**
```bash
echo "engine: claude" >> ~/.speakloop/loop.yaml
```

**Or per-run (flag form):**
```bash
uv run speakloop practice --engine claude     # explicit flag overrides the config default
uv run speakloop resume  --engine claude      # finish any analysis-pending session
```

**Optional model tiering (defaults shown), in `~/.speakloop/loop.yaml`:**
```yaml
engine: claude
claude_fast_model: haiku      # cheap calls: mishearing classification, drills
claude_strong_model: sonnet   # reasoning calls: follow-ups, coverage, consistency, grammar, coach
```

### Two smoke commands you can run yourself
```bash
# 1) Health check — shows the new "Claude Code" section (binary, version, auth, default engine):
uv run speakloop doctor

# 2) A real subscription-billed session through Claude Code:
uv run speakloop practice --engine claude
#    (or finish a pending one:  uv run speakloop resume --engine claude)
```

---

## Assumptions made in your absence

All recorded in `specs/011-claude-code-engine/spec.md` (Assumptions) and `research.md`. The important ones:

1. **`--safe-mode`, NOT `--bare`** (the single most important empirical finding). The plan note said
   use `--bare` for project isolation, but `claude --help` (2.1.170) states `--bare` forces auth to be
   *strictly* `ANTHROPIC_API_KEY`/`apiKeyHelper` (OAuth + keychain never read) — which is incompatible
   with stripping `ANTHROPIC_API_KEY` for billing safety. `--safe-mode` gives the same isolation
   (CLAUDE.md/skills/MCP/hooks/custom-agents disabled) while keeping subscription OAuth working.
2. **`--tools ""`** disables all tools (guarantees a single text-only response), **`--system-prompt`**
   replaces the default system prompt (clean analysis function), **`--no-session-persistence`**.
3. **Key off `is_error`, not `subtype`** (subtype stays `"success"` even on error). Output text is in
   `.result`, may carry ```json fences → left for the existing recovery ladder (no schema/prompt change).
4. **Prompt reuse**: the claude engine reuses the **same editable cloud prompt files** as OpenRouter —
   `~/.speakloop/openrouter_prompt.txt` (grammar) + `~/.speakloop/openrouter_coach_prompt.txt` (coach).
   No new prompt files. (The `openrouter_` name is historical; documented in quickstart.md.)
5. **Tier defaults**: `fast = haiku`, `strong = sonnet`. Opus is intentionally **not** the default
   (conserve subscription credit). Both overridable in `loop.yaml`. The call-site→tier *assignment* is
   fixed in code; only the two tier→model aliases are user-configurable.
6. **Stripped env vars**: `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`,
   `ANTHROPIC_API_URL`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`.
7. **Engine precedence**: explicit `--engine`/`--cloud` flag → `loop.yaml engine:` → built-in `local`.
   Conflicting flags (e.g. `--engine claude --cloud`) or unknown values raise a clear error (exit 2).
8. **Degradation, no auto-fallback**: the claude builder always returns a non-None analyzer, so an
   absent/logged-out Claude Code degrades per-call to `analysis_pending` (resumable) rather than
   silently switching to the local model — matching OpenRouter.
9. **`retry=True`** appends a STRICT-JSON reminder to the *user* prompt (system prompt verbatim),
   mirroring the OpenRouter engine. `max_tokens`/`temperature` are ignored (the CLI exposes neither).
10. **Per-call timeout default 90 s** (spec said "~90s"); fixed, not config-exposed (see Open items).

---

## Deviations from the literal task text

1. **`--bare` → `--safe-mode`** (see assumption #1). This *is* a deviation from the plan-args note; it
   is the correct call and is documented prominently in `research.md` §D2.
2. **Fake-runner harness location**: the task suggested `tests/helpers/fake_claude.py`. I put it in
   `tests/conftest.py` (exposed via the `fake_claude` fixture) because `tests/` is not a package, so a
   `tests/helpers/` module isn't importable across test directories without extra packaging. The
   conftest fixture is the idiomatic, guaranteed-importable choice. (tasks.md T002 still references the
   suggested path.)
3. **P1/P2 split**: US1 shipped the engine with a single (strong) model; US2 added the fast tier via the
   `fast_engine` seam — exactly as tasks.md sequenced it. Both are merged on the branch.

---

## Open items (none blocking)

- **Per-call timeout is fixed at 90 s** (not exposed in `loop.yaml`). The observed worst case (grammar
  on sonnet) was ~60 s, so there is headroom, but if you hit `ClaudeCodeTimeoutError` on long answers,
  raising `_DEFAULT_TIMEOUT` (or adding a `claude_timeout_seconds` loop-config key) is a one-line follow-up.
  Left out of scope tonight (the spec said "default ~90s", not "configurable").
- **Side effect of first claude run**: like the first `--cloud` run, it seeds
  `~/.speakloop/openrouter_prompt.txt` and `openrouter_coach_prompt.txt` from packaged defaults if absent
  (read-if-present, seed-if-absent — non-destructive). The live verification did this on your machine.
- **2 pre-existing `ruff SIM105` findings** in `cli/practice.py` (lines 100/131, the terminal raw-input
  code) were left untouched — they predate this work (present at `b4ac209`) and CLAUDE.md already notes
  `ruff check .` has pre-existing findings. No drive-by cleanups, per your instructions. All **new** code
  is ruff-clean.
- **Grammar latency** (~42–60 s/call on sonnet) — noted above; an inherent cost of a real reasoning call
  through Claude Code, not a defect.

---

## Adversarial review pass

After the tasks finished, I ran one adversarial review over all the new code (per your "if tasks
finish early" instruction): 5 independent review lenses (engine-correctness, billing-security,
cli-wiring, test-quality, constitution-spec) → each finding adversarially verified by a separate
agent before being accepted (13 agents total).

- **No real code defects were found.** Every substantive risk raised was verified and **rejected** as a
  false positive — notably the "doctor_probe doesn't strip billing-override env vars" finding was
  rejected because `doctor_probe` makes **no model call** (just `--version` + `auth status`), so there is
  no billing impact (this matches the FR-007 scope, which targets the analysis subprocess).
- **2 confirmed findings, both LOW severity and test-only** (the implementation was already correct):
  1. No test exercised a non-string `.result` value (e.g. `123`/`true`/`{}`) → added a parametrized test
     (`test_non_string_result_is_bad_output`).
  2. No test asserted a custom `timeout` is threaded to the runner → added
     `test_custom_timeout_is_threaded_to_the_runner`.
- Both fixes are pure test additions (zero production-code change). Suite re-run green: **622 passed**.

## Merge readiness

**Ready for your review and merge.** ✅
- Branch `011-claude-code-engine` pushed; 6 conventional-commit commits; clean working tree.
- Full suite green (`622 passed`); 57 new claude-engine tests; `--help` stays model-free; path-portability
  audit passes; all new files ruff-clean.
- Live-verified 11/11 against the real CLI, including the billing-safety guarantee.
- Constitution-compliant: zero new dependencies, local Qwen stays the default, default path
  byte-identical + offline, engine confined to one wrapper file (Principle V), `schema_version` stays 1,
  no test invokes the real binary.
- **Not merged into `main`** (left for your review, per instructions).

Suggested next step: open a PR from `011-claude-code-engine` → `main` and review the diff
(`git diff main..011-claude-code-engine`).
