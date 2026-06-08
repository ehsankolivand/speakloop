# Data Model: OpenRouter Cloud-Model Provider

This feature introduces **no persisted schema change** — session reports, their
YAML frontmatter, and `schema_version` (1) are untouched. The "data model" here is
the set of small in-memory/config types and on-disk config artifacts the cloud
path uses. Cloud-generated `GrammarPattern` objects are byte-identical in shape to
local ones (same producer pipeline), so the report writer needs no change.

---

## On-disk artifacts (config, not report schema)

### `~/.speakloop/openrouter_token` (NEW)
- **What**: the OpenRouter API token (the secret).
- **Format**: a single plain UTF-8 line, trailing whitespace stripped on read.
- **Permissions**: written `0600`.
- **Lifecycle**: created on first cloud run (interactive capture); read on every
  cloud run; replaced when missing or rejected (re-prompt). Never logged, never
  committed.
- **Precedence**: overridden by env `OPENROUTER_API_KEY` (Decision 4).

### `~/.speakloop/openrouter_prompt.txt` (NEW)
- **What**: the cloud-model system prompt the user edits to tune cloud behavior.
- **Format**: free-form UTF-8 text (the seeded default instructs strict
  `{"errors":[...]}` JSON output the verify/rank pipeline consumes).
- **Lifecycle**: seeded on first cloud run from the packaged default asset; read
  verbatim thereafter. Entirely separate from the local `_SYSTEM_PROMPT`.

### `src/speakloop/feedback/openrouter_prompt_default.txt` (NEW, packaged)
- **What**: the default cloud system prompt shipped in the repo, copied to the
  user file on first run.
- **Constraint**: its own content — it is NOT generated from
  `grammar_analyzer._SYSTEM_PROMPT` (FR-012). Read via `Path(__file__).parent`
  (mirrors `feedback/common_words.txt`).

---

### `~/.speakloop/openrouter.yaml` (NEW — clarified Session 2026-06-08)
- **What**: the cloud settings file; currently a single `model:` key naming the
  OpenRouter model id. (Room to grow later, e.g. `base_url:`/timeout.)
- **Format**: YAML, e.g. `model: qwen/qwen3.7-max`.
- **Lifecycle**: user-edited; absent file or absent `model:` key → default
  `qwen/qwen3.7-max`. Read-only from the app's perspective (not written by it).
- **Why YAML, not env**: honors the constitution's "User configuration: YAML"
  non-negotiable and persists across shells (Decision 5, clarified).

## Settings (resolved)

### OpenRouter model id
- **Path accessor**: `config.paths.openrouter_config_path() -> Path` →
  `~/.speakloop/openrouter.yaml` (pure path; the config leaf stays stdlib-only,
  no YAML read here).
- **Resolver**: `llm.openrouter_config.resolve_model() -> str` reads the YAML
  `model:` key via `pyyaml` (already a dep), else `"qwen/qwen3.7-max"`.
- **Validation**: none locally — an unrecognized id surfaces as an OpenRouter
  error at request time (Edge Cases / FR; SC-004 covers the swap).

---

## In-memory types (private to the cloud path)

### `OpenRouterEngine` (NEW — `llm/openrouter_engine.py`)
Implements the existing `LLMEngine` Protocol; no new public interface.
- **Constructor inputs**: `model: str`, `token: str`,
  optional `timeout: float` (default a small connect/read bound),
  optional `base_url` (default `https://openrouter.ai/api/v1`).
- **`generate(system_prompt, user_prompt, max_tokens=2048, temperature=0.7,
  retry=False) -> str`**: POSTs one chat-completion; returns
  `choices[0].message.content` (stripped). On `retry=True`, the wrapper owns the
  nudge (lower temperature and/or a stronger "STRICT JSON only" reinforcement) —
  the call site passes intent only (Principle V), exactly like `QwenEngine`.
- **`check_auth() -> None`** (or a module function): preflight `GET /key`; raises
  `OpenRouterAuthError` on `401`, `LLMEngineError` on other transport failure.
- **State**: stateless apart from constructor inputs (no model load, no memo).

### `OpenRouterAuthError(LLMEngineError)` (NEW)
- Raised on `401/403`. Lets the build/preflight step distinguish "fix your token"
  (actionable, fail-fast, exit) from generic transient `LLMEngineError` (graceful
  `phase_c_error`).

### Credential resolution (NEW — `llm/openrouter_credentials.py`)
- `resolve_token() -> str | None`: pure precedence env > file > None. No prompting,
  no import-time I/O (mirrors `installer/tokens.py`).
- `store_token(value: str) -> Path`: write `~/.speakloop/openrouter_token` `0600`,
  return the path. Strips surrounding whitespace; refuses empty.

### Cloud prompt loading (NEW — `feedback/cloud_prompt.py`)
- `load_cloud_prompt() -> tuple[str, Path]`: seed-if-missing from the packaged
  default, then read; returns `(prompt_text, user_path)` so the caller can print
  the editable path.

---

## Control-flow types (existing, reused)

### `GrammarPattern` (UNCHANGED — `feedback/frontmatter.py`)
Cloud findings are produced by the same `_verify_and_enrich(...)` path, so the
fields (`label`, `occurrence_count`, `explanation`, `evidence[]`, `suggested_fix`,
`impact_rank`, `catalog_id`) and their semantics are identical to local mode. The
report renders identically.

### `analyze(...)` signature delta (ADDITIVE — `feedback/grammar_analyzer.py`)
- Before: `analyze(transcripts, llm, *, max_tokens=2048)`.
- After: `analyze(transcripts, llm, *, max_tokens=2048, system_prompt=None)`.
- `system_prompt=None` → use module-local `_SYSTEM_PROMPT` (local behavior
  byte-identical). Cloud passes the loaded cloud prompt. This is the only
  shared-code shape change in the feature.

---

## State transitions — token lifecycle (cloud mode)

```text
        ┌────────────────────────── speakloop practice --cloud ──────────────────────────┐
        │                                                                                  │
   resolve_token()                                                                         │
        │                                                                                  │
   env OPENROUTER_API_KEY set? ──yes──► token = env ─┐                                      │
        │no                                          │                                      │
   ~/.speakloop/openrouter_token exists? ──yes──► token = file ─┤                           │
        │no                                                      │                          │
   PROMPT once (+ privacy disclosure) ──► store_token() ─────────┤                          │
        │ (declined/empty)                                       │                          │
        ▼                                                        ▼                          │
   actionable error → exit(1)                            PREFLIGHT check_auth()             │
                                                                 │                          │
                                          401 ◄──────────────────┤──────────────► 200 OK    │
                                           │                                        │        │
                              actionable error + re-prompt once                build engine  │
                                           │ (still bad)                            │        │
                                           ▼                                        ▼        │
                                       exit(1)                       run session → analyze(..., system_prompt=cloud_prompt)
                                                                                    │        │
                                                          transient OpenRouter failure → LLMEngineError
                                                                                    │        │
                                                          coordinator try/except → phase_c_error (debrief preserved)
        └──────────────────────────────────────────────────────────────────────────────────┘
```

Default (no `--cloud`): none of the above runs; `_build_grammar_analyzer()`
behaves exactly as today (validate local Qwen → `QwenEngine` → `analyze(...)` with
the local prompt) and no token is ever read or requested.
