# Phase 1 Data Model — Claude Code Analysis Engine

This feature adds **no persisted data entities** (no new store, no frontmatter keys). The "entities"
below are in-memory types and config fields.

## ClaudeCodeEngine (new class — `llm/claude_code_engine.py`)

Implements the existing `LLMEngine` Protocol.

| Field | Type | Notes |
|-------|------|-------|
| `model` | `str` | model alias passed to `--model` (e.g. `"haiku"`, `"sonnet"`) |
| `runner` | `Callable[[list[str], str, float, dict[str,str]], ClaudeCliResult]` | **injectable**; defaults to the real `subprocess` runner. Tests inject a fake. |
| `timeout` | `float` | hard per-call timeout, default `90.0` s |
| `binary` | `str` | binary name, default `"claude"` (resolved on PATH) |

Method: `generate(system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False) -> str`
- `max_tokens` and `temperature` are **ignored** (CLI exposes neither; documented in docstring).
- `retry=True` → append a STRICT-JSON reminder to `user_prompt`; `system_prompt` kept verbatim.
- Builds argv (D2), invokes `runner`, parses the envelope (D3), returns `result` or raises (D4).

## ClaudeCliResult (new dataclass)

The runner's return value — what the engine parses. Decouples the engine from `subprocess`.

| Field | Type | Notes |
|-------|------|-------|
| `stdout` | `str` | the JSON envelope (or garbage on failure) |
| `stderr` | `str` | captured for error messages |
| `returncode` | `int` | process exit code |

The runner raises `FileNotFoundError` (binary missing) and `subprocess.TimeoutExpired` (timeout)
directly; the engine translates those into the taxonomy.

## Error taxonomy (new `LLMEngineError` subclasses)

All inherit `llm.interface.LLMEngineError` so the coordinator degradation is unchanged.

| Class | Trigger | Message theme |
|-------|---------|---------------|
| `ClaudeCodeNotInstalledError` | `FileNotFoundError` from runner | "Claude Code CLI not found on PATH …" |
| `ClaudeCodeAuthError` | `is_error` + login text | "Claude Code is not logged in (run `claude /login`) …" |
| `ClaudeCodeRateLimitError` | `is_error` + rate/limit/quota/credit text | "Claude Code usage/rate limit reached …" |
| `ClaudeCodeTimeoutError` | `subprocess.TimeoutExpired` | "Claude Code call exceeded {timeout}s …" |
| `ClaudeCodeBadOutputError` | JSON parse failure / unknown-flag stderr / unexpected shape | "Claude Code returned unexpected output (CLI may have changed) …" |

## Engine selection (resolved per run)

Precedence (highest wins): **explicit flag → loop-config `engine` → built-in `"local"`**.

| Input | Resolves to |
|-------|-------------|
| `--engine local\|openrouter\|claude` | that engine |
| `--cloud` | `openrouter` (alias) |
| `--engine X` **and** `--cloud` where X≠openrouter | error (conflict) |
| neither flag, `loop.yaml engine: claude` | `claude` |
| neither flag, no config | `local` |

Valid values: `{local, openrouter, claude}`. Unknown value → clear error listing valid choices.

## Model tier map (P2)

Static `CALL_SITE_TIER` (in the CLI builder / engine module):

```
fast   = {mishearing, drill}
strong = {followups, keypoints, coverage, consistency, grammar, coach}
```

Tier → model alias, from `LoopConfig`:
- `fast`  → `claude_fast_model`  (default `"haiku"`)
- `strong`→ `claude_strong_model` (default `"sonnet"`)

## LoopConfig additions (additive, optional)

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `engine` | `str` | `"local"` | default analysis engine when no flag given |
| `claude_fast_model` | `str` | `"haiku"` | model alias for the `fast` tier |
| `claude_strong_model` | `str` | `"sonnet"` | model alias for the `strong` tier |

Absent/invalid → defaults (mirrors existing `LoopConfig` tolerance). `schema_version` unaffected
(this is user config, not the report).
