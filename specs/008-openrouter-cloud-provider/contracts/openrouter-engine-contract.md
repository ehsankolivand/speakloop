# Contract: OpenRouter Engine

**File**: `src/speakloop/llm/openrouter_engine.py` — the ONLY file in the repo
that talks to OpenRouter. Implements the existing `speakloop.llm.LLMEngine`
Protocol; adds no new public interface beyond the typed auth error.

## Constants (pinned here)

| Constant | Value |
|---|---|
| Base URL | `https://openrouter.ai/api/v1` |
| Chat endpoint | `POST {base}/chat/completions` |
| Auth check endpoint | `GET {base}/key` |
| Auth header | `Authorization: Bearer <token>` |
| Content type | `application/json` |
| Default timeout | bounded connect+read (e.g. 30 s) — never block forever |

## `generate(...)` request shape

`generate(system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False) -> str`

POST body (OpenAI-compatible):
```json
{
  "model": "<openrouter_config.resolve_model()>",
  "messages": [
    {"role": "system", "content": "<system_prompt>"},
    {"role": "user", "content": "<user_prompt>"}
  ],
  "temperature": <temperature>,
  "max_tokens": <max_tokens>
}
```

Invariants:
- The `system` message content is **exactly** the `system_prompt` argument the
  caller passed (in cloud mode: the loaded cloud prompt file). The engine MUST NOT
  substitute or ignore it.
- The bearer token is the resolved credential; it MUST NOT be logged or included
  in any error message.
- `retry=True` is intent-only: the wrapper owns any anti-degenerate nudge (e.g.
  lower temperature, reinforce "STRICT JSON only"). The call site never passes
  sampler/penalty config (Principle V), exactly as with `QwenEngine`.

## `generate(...)` response handling

- On HTTP 200: parse JSON, return `choices[0].message.content` with surrounding
  whitespace stripped. (No `<think>`-stripping is assumed necessary; the analyzer's
  existing fence/`json-repair` recovery handles any wrapping.)
- The returned string is fed unchanged into the analyzer's `_extract_json(...)`
  recovery ladder — so the cloud model is expected to emit the same strict
  `{"errors":[...]}` schema the local prompt requests.

## Error mapping (test invariants)

| Condition | Raised |
|---|---|
| HTTP 401 / 403 | `OpenRouterAuthError` (subclass of `LLMEngineError`) |
| HTTP 404 (unknown model id) | `LLMEngineError` with a message naming the model id |
| HTTP 5xx | `LLMEngineError` |
| Connection error / timeout | `LLMEngineError` |
| 200 but missing `choices[0].message.content` | `LLMEngineError` |

- `OpenRouterAuthError` exists so the build/preflight step can fail fast with an
  actionable message (FR-006), while every other failure is a generic
  `LLMEngineError` that the coordinator degrades gracefully into `phase_c_error`
  (FR-014/SC-007).
- No error message may contain the token value.

## `check_auth()` (preflight)

- `GET {base}/key` with the bearer header.
- 200 → return (token valid). 401/403 → raise `OpenRouterAuthError`. Other
  transport failure → `LLMEngineError`.
- Cheap, single request; run once at cloud-analyzer build time before the timed
  session (Decision 8).

## Import / offline invariants

- Imports only stdlib (`urllib.request`, `urllib.error`, `json`) plus
  `speakloop.llm.interface` — **no engine package, no third-party HTTP client**.
- No network call at import time; calls happen only inside `generate()` /
  `check_auth()`.
- Imported function-local from the CLI (like `QwenEngine`), so
  `tests/integration/test_help_without_models.py` still sees no engine packages
  loaded by importing the CLI.

## Unit-test checklist (mock `urllib`, no live call)

- [ ] Request URL, method, headers (bearer present), and JSON body match the shape
      above for given args.
- [ ] `system` message equals the passed `system_prompt` verbatim.
- [ ] 200 → returns `choices[0].message.content` stripped.
- [ ] 401 → `OpenRouterAuthError`; 404 → `LLMEngineError` naming the model;
      5xx/timeout → `LLMEngineError`.
- [ ] Token never appears in any raised message.
- [ ] `retry=True` changes the request (documented nudge) but still posts valid
      JSON.
- [ ] `check_auth()` hits `/key` and maps 200/401/other correctly.
