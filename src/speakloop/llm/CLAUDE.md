# llm

## Purpose

LLM engine wrapper for educational grammar/coherence feedback [Phase C]. Ships Qwen3-14B
(MLX 4-bit) as the local default, plus OpenRouter (008) and Claude Code CLI (011), all
behind one stable `LLMEngine` Protocol so swapping the model touches exactly one file.

## Public interface

- `interface.LLMEngine` (Protocol) — `generate(system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False) -> str`. `retry=True` signals bounded regenerate; callers pass intent only, never engine config (root CLAUDE.md O5).
- `interface.LLMEngineError` — single public error base; all engine errors subclass it.
- `claude_code_engine.ClaudeCodeEngine` — subclasses: `ClaudeCodeError`, `ClaudeCodeNotInstalledError`, `ClaudeCodeAuthError`, `ClaudeCodeRateLimitError`, `ClaudeCodeTimeoutError`, `ClaudeCodeBadOutputError`.
- `claude_code_engine.build_env()` — strips billing-override env vars.
- `claude_code_engine.doctor_probe()` — credit-free version/auth check for `speakloop doctor`.
- `openrouter_engine.OpenRouterAuthError(LLMEngineError)` / `check_auth()` — preflight fail-fast.

## parallel_safe convention

`parallel_safe` is NOT on the `LLMEngine` Protocol (`interface.py` has no such attribute).
It is a **per-class attribute** each engine declares manually:
- `QwenEngine.parallel_safe = False` (`qwen_engine.py:47`) — single in-process MLX model; concurrent calls contend on one set of weights.
- `OpenRouterEngine.parallel_safe = True` (`openrouter_engine.py:41`) — independent HTTP requests.
- `ClaudeCodeEngine.parallel_safe = True` (`claude_code_engine.py:183`) — each call is a separate subprocess; process isolation makes concurrent runs safe.

New engines MUST declare `parallel_safe` manually; omitting it causes `getattr(..., False)` in the coordinator to silently force serial mode.

## Claude Code CLI contract (O13 — owned here)

Pinned to observed `claude 2.1.170` (`claude_code_engine.py:39`). Flags (all named constants):
`--print --output-format json --model <alias> --safe-mode --tools "" --no-session-persistence --system-prompt <prompt>`, user prompt on stdin.

- Keys off envelope `is_error` (`claude_code_engine.py:58`), NOT `subtype` (stays "success" even on error).
- `--safe-mode` NOT `--bare`: `--bare` forces `ANTHROPIC_API_KEY`/keychain auth and breaks subscription billing after the env strip.
- `STRIPPED_ENV_VARS` = 6 vars (`claude_code_engine.py:63-70`): `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_URL`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`. Must not shrink.
- `_DEFAULT_TIMEOUT = 90.0` (`claude_code_engine.py:72`); loop.yaml `claude_timeout_seconds` default is 240 (`config/loop_config.py:28`).
- `generate()` ignores `max_tokens` and `temperature` (CLI has neither).
- `doctor_probe()` and `default_runner()` are the two spawners; `default_runner` is the test injection seam.

## Qwen generation config (O5 — owned here)

All config lives in `qwen_engine.py`; the analyzer passes `temperature=0.3` and `retry` only.
`make_sampler`: top_p=0.8, top_k=20, min_p=0. `make_logits_processors`: repetition_penalty=1.05, context=40. `retry=True` raises penalty → 1.15, lowers temperature by 0.1. Defensive EOS `<|im_end|>` is wrapper-side truncation (no `stop=` kwarg in mlx-lm). Thinking mode ON; leading `<think>...</think>` stripped by `_LEADING_THINK_RE` (non-greedy DOTALL); truncated thinking (missing `</think>`) is NOT auto-scrubbed — the analyzer's bounded regenerate catches it.

## Dependencies

- `mlx_lm` — function-local in `qwen_engine.py` only (Principle V; root CLAUDE.md O1).
- `urllib` (stdlib) — `openrouter_engine.py` only; no new dep.
- `subprocess` (stdlib) — `claude_code_engine.py` only; no new dep.
- Internal: `speakloop.installer` (model paths), `speakloop.config` (paths + loop config).

## Consumers

`cli` (engine selection + `doctor_probe`), `feedback` (grammar analyzer, coach).

## File map

- `interface.py` — `LLMEngine` Protocol + `LLMEngineError`.
- `qwen_engine.py` — `QwenEngine`; the ONLY `import mlx_lm`; Qwen3-14B 4-bit; lazy load; thinking strip; `parallel_safe = False`.
- `openrouter_engine.py` (008) — `OpenRouterEngine`; stdlib `urllib`; `OpenRouterAuthError`; `check_auth()`; `parallel_safe = True`.
- `openrouter_credentials.py` (008) — `resolve_token()` (env `OPENROUTER_API_KEY` > `~/.speakloop/openrouter_token` > None); `store_token()` (0600). No import-time I/O.
- `openrouter_config.py` (008) — `resolve_model()` from `~/.speakloop/openrouter.yaml`; absent/malformed → default `qwen/qwen3.7-max`.
- `claude_code_engine.py` (011) — `ClaudeCodeEngine`; the ONLY subprocess spawner of `claude`; `build_env()`; `doctor_probe()`; `parallel_safe = True`.

## Common modification patterns

- **Add an engine**: implement `LLMEngine` in a new `*_engine.py`, keep package imports function-local, declare `parallel_safe`, touch no other module.
- **Change generation config**: edit `qwen_engine.py` only; never let a call site set repetition_penalty/top_p/top_k/stop.
- **Change the model**: update `installer/manifest.py`; not here.

## Traps

- `parallel_safe` is per-class convention, not Protocol — omitting it silently forces serial.
- Qwen3-14B 4-bit is the current ship; 6-bit exceeded M3 Pro 18 GB budget alongside Whisper. 8-bit out of scope. See `doc/research_llm.md` (Update 2026-05-25).
- LLM-caller rules (ideal_answer boundary, degradation contract): `.claude/rules/llm-calls.md`.
- Test rules (inject fake runner, never real binary): `.claude/rules/testing.md`.

## Pointers

- Root map: `../../../CLAUDE.md` (engine-import-function-local O1, schema_version O3).
- Research: `doc/research_llm.md`. Claude Code contract: `specs/011-claude-code-engine/research.md`.
