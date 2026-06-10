# Phase 0 Research — Claude Code Analysis Engine

All findings below were **verified empirically** against the installed CLI on the development
machine, not taken from documentation. Each pinned behavior becomes a named constant in
`claude_code_engine.py` with a comment citing the observed version, so a future incompatible CLI
change fails loudly in exactly one place (FR-009).

**Observed CLI**: `claude 2.1.170 (Claude Code)` — path `/Users/<user>/.local/bin/claude`
(resolved via `shutil.which("claude")`). Date observed: 2026-06-10.

---

## D1 — Transport: subprocess vs Agent SDK

**Decision**: Drive the installed `claude` binary via `subprocess`, stdlib only.

**Rationale**: Zero new dependencies (Constitution: "standard library over dependencies"), and
mirrors the established pattern where `openrouter_engine.py` is the only `urllib` caller. One
process per `generate()` call keeps the engine stateless and trivially testable with an injected
fake runner.

**Alternatives considered**:
- **Python `claude-agent-sdk`** — rejected. It is an extra third-party dependency that ultimately
  shells out to / wraps the same Claude Code product with the same subscription-credit coverage, so
  it buys nothing over `subprocess` while violating the zero-new-dependency constraint.
- **Direct HTTP to the Anthropic API with the subscription OAuth token** — rejected and explicitly
  out of scope (ToS risk; the feature must drive the genuine product).

---

## D2 — Invocation flags (the pinned CLI contract)

**Decision**: One invocation per call:

```
claude --print --output-format json --model <ALIAS> --safe-mode --tools "" \
       --no-session-persistence --system-prompt <SYSTEM_PROMPT>
# user prompt piped on stdin
```

Empirically verified flags (from `claude --help`, v2.1.170):

| Flag | Why | Observed behavior |
|------|-----|-------------------|
| `--print` / `-p` | non-interactive single response | prints result and exits |
| `--output-format json` | structured single envelope | emits one JSON object (see D3) |
| `--model <alias>` | per-call model (tiering) | `haiku` → `claude-haiku-4-5-20251001`; `sonnet`/`opus` also valid aliases |
| `--safe-mode` | project isolation **without breaking auth** | "disables CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands and agents …; Auth, model selection, built-in tools, and permissions work normally" |
| `--tools ""` | guarantee a single text-only response, no tool use | help: `Use "" to disable all tools` |
| `--no-session-persistence` | don't litter session history | "sessions will not be saved to disk" (print-only) |
| `--system-prompt <p>` | replace default system prompt with our analysis prompt | clean JSON-producing function, no agentic preamble |
| stdin | user prompt | piped content becomes the prompt in `-p` mode (verified) |

### ⚠ Empirical correction: `--safe-mode`, NOT `--bare`

The original plan note proposed `--bare` for project isolation. **This is wrong for our billing
model.** `claude --help` for `--bare` states verbatim:

> Anthropic auth is **strictly** `ANTHROPIC_API_KEY` or `apiKeyHelper` via `--settings` (**OAuth and
> keychain are never read**).

Because the billing-safety requirement (FR-007) **strips** `ANTHROPIC_API_KEY` from the subprocess,
`--bare` would leave the call with **no credentials at all** → guaranteed auth failure. `--safe-mode`
achieves the same isolation goals (no CLAUDE.md/skills/plugins/hooks/MCP/custom-agents) **while
keeping subscription OAuth working normally**. This is the single most important finding of Phase 0.

---

## D3 — Success envelope shape

**Decision**: Parse stdout as JSON; on success return the `result` string verbatim (the existing
JSON-recovery ladder strips any markdown fences).

Observed success envelope (`--output-format json`, model `haiku`):

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "```json\n{\"ok\": true}\n```",
  "stop_reason": "end_turn",
  "session_id": "...",
  "total_cost_usd": 0.001196,
  "usage": { "...": "..." },
  "modelUsage": { "claude-haiku-4-5-20251001": { "...": "..." } },
  "permission_denials": [],
  "terminal_reason": "completed"
}
```

Pinned facts:
- The model's text output is in **`result`** (a string).
- **The output may be wrapped in ` ```json … ``` ` fences** even when the prompt says "JSON only".
  This is fine — `feedback/grammar_analyzer._extract_json` already strips fences (no prompt change).
- **Success is keyed on `is_error == false`, NOT on `subtype`** — see D4: `subtype` stays `"success"`
  even on error.
- Exit code `0` on success.

---

## D4 — Error taxonomy (failure detection)

**Decision**: Map failures to `LLMEngineError` subclasses so the coordinator's existing
`analysis_pending` degradation works unchanged.

| Observed condition | Detection | Engine error |
|--------------------|-----------|--------------|
| binary missing | `subprocess` raises `FileNotFoundError` (shell analog: exit 127) | `ClaudeCodeNotInstalledError` |
| call exceeds timeout | `subprocess.TimeoutExpired` | `ClaudeCodeTimeoutError` |
| not logged in / logged out | envelope `is_error: true`, `result` ≈ `"Not logged in · Please run /login"`, `total_cost_usd: 0`, `modelUsage: {}` | `ClaudeCodeAuthError` |
| rate/usage/credit exhausted | `is_error: true`, `result`/`api_error_status` text matches `rate`/`limit`/`quota`/`credit`/`overloaded` | `ClaudeCodeRateLimitError` |
| non-JSON / truncated stdout | `json.loads` fails | `ClaudeCodeBadOutputError` |
| unknown flag (auto-update changed a flag) | exit ≠ 0, **no JSON on stdout**, stderr begins `error: unknown option …` | `ClaudeCodeBadOutputError` (fail loudly) |

Verified observations:
- **Auth failure** (simulated safely via `--bare` with no key — never logs out the real session):
  exit `1`, stdout is a JSON envelope with `"is_error": true`, `"subtype": "success"` (hence we MUST
  key off `is_error`), `"result": "Not logged in · Please run /login"`, `total_cost_usd: 0`. $0
  billed.
- **Unknown flag**: exit `1`, stderr `error: unknown option '--this-flag-was-removed'`, **no stdout**
  → not parseable as the success envelope → `bad_output`.

All subclasses inherit `LLMEngineError`, so `sessions/coordinator.py`'s `except Exception` (grammar)
and the best-effort `except Exception` blocks (coverage, mishearing, consistency, etc.) catch them
identically to today and set `analysis_pending` / return empty.

---

## D5 — Credit-free authentication check (for `doctor`)

**Decision**: Use `claude auth status --json` — it performs **no model call** (no credit) and is the
cheapest reliable auth probe.

Observed (logged in):

```json
{ "loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty",
  "email": "…", "orgId": "…", "orgName": "…", "subscriptionType": "max" }
```

Observed with a stray `ANTHROPIC_API_KEY` set (dummy): an extra field appears —
`"apiKeySource": "ANTHROPIC_API_KEY"` and the subscription fields go null. So **doctor can detect the
pay-per-token billing risk**: if `ANTHROPIC_API_KEY` is present in the environment, warn that the
claude engine will strip it to protect subscription billing.

Doctor rows (FR-008):
1. **binary present** — `shutil.which("claude")` → OK/path or WARN/not-found.
2. **version** — `claude --version` (local, free).
3. **auth state** — `claude auth status --json` → `loggedIn`/`authMethod`/`subscriptionType`.
4. **configured default engine** — from `loop_config.load().engine`.
   (+ informational WARN if `ANTHROPIC_API_KEY` is set in the ambient environment.)

> Testability: the doctor claude-probe is written so tests monkeypatch the `which`/run helpers — no
> automated test runs the real binary.

---

## D6 — Billing safety (hard requirement, FR-007)

**Decision**: Build the subprocess environment from a **copy** of `os.environ` with these keys
removed:

```
ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL, ANTHROPIC_API_URL,
CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_USE_VERTEX
```

**Rationale**: Claude Code documented behavior **prefers** an `ANTHROPIC_API_KEY` over subscription
auth — leaving it set would silently bill pay-per-token. Stripping these (and the Bedrock/Vertex
toggles, which reroute to a third-party billed endpoint) forces subscription OAuth. `--safe-mode`
(D2) keeps OAuth working after the strip. A unit test asserts the env handed to the runner never
contains `ANTHROPIC_API_KEY`, even when `os.environ` does.

---

## D7 — Impedance mismatches (temperature / max_tokens / retry)

- The CLI exposes **no** `--temperature` or `--max-tokens`. Per the existing "engine owns generation
  details" contract (Principle V), `ClaudeCodeEngine.generate()` **ignores** both parameters and
  documents this in its docstring; output quality relies on strict-JSON prompting plus the existing
  recovery ladder (which already tolerates fences and minor noise).
- `retry=True` maps to **one bounded re-invocation**: append a STRICT-JSON reminder to the **user**
  prompt, keeping the **system** prompt verbatim — identical in spirit to `OpenRouterEngine`.

---

## D8 — Model tiering (P2)

**Decision**: A static call-site→tier map; tier→model is configurable.

| Tier | Default model alias | Call sites |
|------|---------------------|------------|
| `fast` | `haiku` | mishearing classification, drill generation |
| `strong` | `sonnet` | follow-ups, key-points, coverage + content errors, artifact consistency, grammar, coach |

**Rationale**: Conserve subscription credit by sending mechanical classification to a cheap model and
reasoning-heavy analysis to a strong (but not maximal — Opus is intentionally not the default) model.
`fast`/`strong` model aliases are overridable via `claude_fast_model` / `claude_strong_model` in
`loop.yaml`. The call-site→tier assignment is fixed in code (a sensible default); finer per-call-site
override is out of scope.

**Wiring** (zero call-site changes): construct one `ClaudeCodeEngine` per tier in the CLI builder and
inject the tier-appropriate instance into each runner. `_build_runners(engine, *, fast_engine=None)`
gains an optional `fast_engine` that **defaults to `engine`**, so the local/openrouter wiring stays
byte-identical; only the claude builder passes a distinct `fast_engine`.

---

## D9 — Degradation & no auto-fallback

**Decision**: The claude builder **always returns a non-None analyzer** (unlike the local builder,
which returns None when Qwen is absent). If Claude Code is absent/logged-out, each `generate()`
raises an `LLMEngineError` subclass → the coordinator catches it → `analysis_pending=True`, report
written, session resumable (SC-003). It does **not** auto-fall-back to local Qwen — matching the
OpenRouter engine, which degrades rather than silently switching engines. A free `shutil.which`
heads-up is printed up front so the learner knows analysis will be pending, but the session still
records audio + transcripts + the deterministic report.

---

## D10 — Prompt reuse

**Decision**: The claude builder reuses the **same editable cloud prompt files** the OpenRouter path
uses for grammar (`~/.speakloop/openrouter_prompt.txt`) and coach
(`~/.speakloop/openrouter_coach_prompt.txt`), and the interview-loop runners use their existing
shared seeded prompts. **No new or changed prompt files** (out of scope per spec). The slight naming
wart (an `openrouter_*` prompt used by the claude engine) is documented in quickstart.md; it is the
minimal in-scope choice and keeps grammar/coach behavior "identical to the OpenRouter engine."
