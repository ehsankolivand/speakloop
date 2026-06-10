# llm

## Purpose

LLM engine wrapper for educational grammar/coherence feedback [Phase C]. Ships **Qwen3-14B
(MLX 4-bit)** as the local default, plus an **opt-in OpenRouter cloud engine** (008), both
behind one stable interface so the model can be swapped in one file (Principle V).

## Public interface

- `interface.LLMEngine` (Protocol) — the stable contract consumers depend on.
- `interface.LLMEngineError`.
- `claude_code_engine.ClaudeCodeEngine` (011) — a third engine driving the local Claude Code
  CLI; `ClaudeCodeError` + subclasses (`ClaudeCodeNotInstalledError`, `…AuthError`,
  `…RateLimitError`, `…TimeoutError`, `…BadOutputError`) all subclass `LLMEngineError`.
  `doctor_probe()` is a credit-free version/auth check for `speakloop doctor`.

## Dependencies

- **Engine package owned here (Principle V — function-local):** `mlx_lm` → `qwen_engine.py`.
  `qwen_engine.py` is the ONLY file in the repo that imports `mlx_lm`.
- **Cloud engine (008):** `openrouter_engine.py` is the ONLY file that talks to OpenRouter,
  over **stdlib `urllib`** (no new dependency). `openrouter_config.py` reads the model id from
  `~/.speakloop/openrouter.yaml` (`pyyaml`, already a dep); `openrouter_credentials.py` is a
  pure token resolver (env > file).
- **Claude Code engine (011):** `claude_code_engine.py` is the ONLY file that spawns the
  `claude` subprocess (stdlib `subprocess`, no new dependency — mirrors the OpenRouter pattern).
  Selected via `--engine claude` / `loop.yaml engine:`; subscription-billed; reuses the cloud
  prompt files. NEVER imports an engine package.
- Internal: `speakloop.installer` (model paths/manifest), `speakloop.config` (cloud paths +
  loop config for the engine default + model tiers).

## Consumers

`cli`, `feedback`.

## File map

- `interface.py` — `LLMEngine` Protocol + `LLMEngineError`. `generate(...)` takes an
  additive optional `retry` flag (intent only — the wrapper owns the engine config).
- `qwen_engine.py` — `QwenEngine`; the only `import mlx_lm`; lazy load + the full
  generation config. Qwen3-14B at MLX 4-bit; **thinking mode ON**; the leading
  `<think>...</think>` block is stripped at the wrapper boundary (leading-only regex)
  so callers see clean JSON-ready output. `make_sampler` uses the caller's
  `temperature` (analyzer passes 0.3; Protocol default 0.7) with top_p 0.8 / top_k 20 /
  min_p 0; `make_logits_processors` applies repetition_penalty 1.05 / context 40.
  `retry=True` raises repetition_penalty → 1.15 and lowers temperature by 0.1 for the
  analyzer's one bounded regenerate.
- `openrouter_engine.py` (008) — `OpenRouterEngine(LLMEngine)` over stdlib `urllib`; POSTs to
  OpenRouter's OpenAI-compatible `/chat/completions`, returns `choices[0].message.content`.
  Adds `OpenRouterAuthError(LLMEngineError)` for 401/403 (so the CLI fails fast at preflight)
  and `check_auth()` (`GET /key`). `retry=True` nudges the USER message (STRICT-JSON reminder)
  + lowers temperature, keeping the **system** message verbatim. The token is never logged.
- `openrouter_credentials.py` (008) — `resolve_token()` (env `OPENROUTER_API_KEY` >
  `~/.speakloop/openrouter_token` > None) + `store_token()` (0600). No interactive/import-time
  I/O (interactive prompt lives in `cli/practice.py`).
- `openrouter_config.py` (008) — `resolve_model()` reads the `model:` key from
  `~/.speakloop/openrouter.yaml` (default `qwen/qwen3.7-max`); absent/malformed → default.
- `claude_code_engine.py` (011) — `ClaudeCodeEngine(LLMEngine)` driving the local Claude Code
  CLI via stdlib `subprocess`. The ONLY file that spawns `claude`. Invocation pinned to observed
  `claude 2.1.170` as named constants: `--print --output-format json --model <alias> --safe-mode
  --tools "" --no-session-persistence --system-prompt`, user prompt on stdin. **Keys off
  envelope `is_error`** (NOT `subtype`); returns `.result` (fences left for the recovery ladder).
  `build_env()` strips `ANTHROPIC_API_KEY` + related override vars (billing safety: Claude Code
  prefers the env key → pay-per-token). `generate()` IGNORES `max_tokens`/`temperature` (CLI has
  neither); `retry=True` appends a STRICT-JSON reminder to the USER prompt (system verbatim).
  Failures → `ClaudeCodeError` subclasses (all `LLMEngineError`) → coordinator `analysis_pending`.
  `default_runner` is injectable (tests pass a fake; no test spawns the real binary).

## Common modification patterns

- **Swap the LLM**: implement `LLMEngine` in a new `*_engine.py`, keep its package import
  function-local, point the model id at the manifest entry. Touch no other module.
- **Cloud is engine-only**: cloud mode reuses the entire `feedback/grammar_analyzer.py`
  verify/rank pipeline; the only difference is which engine + which system prompt
  `analyze(...)` receives. The local Qwen flow is untouched by cloud mode.
- **Change the model build**: edit the manifest entry in `installer/manifest.py`, not here.

## Traps

- **Research and manifest agree.** The prior Qwen3.5-9B-VLM divergence is **closed**;
  `doc/research_llm.md` (Update — 2026-05-25) and `installer/manifest.py` both target
  **Qwen3-14B at MLX 4-bit** (re-quantised down from 6-bit because the 6-bit variant
  exceeded the M3 Pro 18 GB resident-RAM budget alongside resident Whisper). Do not
  reintroduce divergence without a fresh research entry.
- **Thinking mode is enabled; `<think>...</think>` blocks are stripped at the wrapper
  boundary.** The strip is leading-only (regex
  `^\s*<think>.*?</think>\s*`). A truncated thinking pass (missing `</think>`) is NOT
  auto-scrubbed; the analyzer's bounded regenerate path catches that case. Tests must
  cover BOTH the strip behavior AND pass-through of think-free output.
- **All generation config lives HERE, not at the call site** (Principle V). The
  analyzer passes intent only (`retry`) plus `temperature=0.3`; it never sets
  repetition_penalty / top_p / top_k / stop.
- **mlx-lm's generate has no `stop=` parameter** — the defensive EOS (`<|im_end|>`) is
  applied by truncating in `_strip_artefacts`, not by a generate kwarg.
- **4-bit at the 14B size is the current ship.** 6-bit at 14B (~12 GB on disk, ~14 GB
  resident) exceeded the M3 Pro 18 GB target's unified-memory budget when loaded alongside
  resident Whisper-large-v3-turbo. 4-bit (~8 GB on disk, ~10 GB resident) is the right
  precision for that hardware target. 8-bit stays out of scope.

## Never do

- Import `mlx_lm` anywhere but `qwen_engine.py`, or at module top level (Principle V/VIII).
- Talk to OpenRouter from any file but `openrouter_engine.py`; add a non-stdlib HTTP client
  (stdlib `urllib` is the chosen transport); log the token; or make the cloud network call on
  any non-`--cloud` path (Principle II — the default stays offline; 008).
- Spawn the `claude` subprocess from any file but `claude_code_engine.py` (011). Don't switch it
  to `--bare` (that forces `ANTHROPIC_API_KEY`/keychain auth and breaks subscription billing —
  use `--safe-mode`); don't stop stripping the billing-override env vars; don't let an automated
  test invoke the real `claude` binary (inject a fake runner).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md); research: `doc/research_llm.md`.
