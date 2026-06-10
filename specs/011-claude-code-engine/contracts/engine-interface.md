# Contract — ClaudeCodeEngine ↔ LLMEngine

`claude_code_engine.py` is the **only** file that spawns the `claude` subprocess (Principle V).

## generate() contract

```python
def generate(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048, temperature: float = 0.7,
             retry: bool = False) -> str: ...
```

- **Returns**: the model's text (`envelope["result"]`), stripped. Callers run it through the existing
  `_extract_json` recovery ladder — markdown fences in `result` are expected and tolerated.
- **Ignores** `max_tokens` and `temperature` (CLI has no such flags) — documented in the docstring.
- `retry=True`: append a STRICT-JSON reminder to `user_prompt`; **`system_prompt` is sent verbatim**.
- **Raises** an `LLMEngineError` subclass on any failure (taxonomy below) — never returns junk.

## argv (pinned to observed `claude 2.1.170` — named constants with version-citing comments)

```
claude --print --output-format json --model <self.model> --safe-mode --tools "" \
       --no-session-persistence --system-prompt <system_prompt>
```
- `user_prompt` is written to the process **stdin**.
- `--safe-mode` (NOT `--bare`): isolates from project CLAUDE.md/skills/MCP/hooks while keeping
  subscription OAuth. (`--bare` would require `ANTHROPIC_API_KEY`, which we strip → would fail.)
- `--tools ""`: no tool use → single text-only response.

## Environment (billing safety — FR-007)

The runner is given `env = {**os.environ}` with these keys **removed**:
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_URL`,
`CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`.

**Guarantee (tested)**: the env handed to the runner never contains `ANTHROPIC_API_KEY`, even when
`os.environ` does.

## Envelope parsing (D3/D4)

1. Runner raises `FileNotFoundError` → `ClaudeCodeNotInstalledError`.
2. Runner raises `subprocess.TimeoutExpired` → `ClaudeCodeTimeoutError`.
3. `json.loads(stdout)` fails → `ClaudeCodeBadOutputError` (include stderr head; likely a CLI change).
4. `envelope["is_error"] is True` → classify by `result` / `api_error_status` text:
   - matches login/logged-out → `ClaudeCodeAuthError`
   - matches rate/limit/quota/credit/overloaded → `ClaudeCodeRateLimitError`
   - else → generic `LLMEngineError`
5. Missing `result` key, or `result` not a string → `ClaudeCodeBadOutputError`.
6. Otherwise return `str(envelope["result"]).strip()`.

> Key off **`is_error`**, never `subtype` (which stays `"success"` even on error).

## Contract test (no real binary)

`tests/contract/test_llm_interface.py` is parametrized over `ClaudeCodeEngine(runner=fake)` where
`fake` returns a canned success `ClaudeCliResult`. Asserts `generate("sys","user")` returns the
expected string and that `LLMEngineError` subclasses are `Exception`s. The existing `StubLLMEngine`
test stays green.
