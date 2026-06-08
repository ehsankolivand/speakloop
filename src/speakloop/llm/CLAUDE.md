# llm

## Purpose

LLM engine wrapper for educational grammar/coherence feedback [Phase C]. Ships **Qwen3-14B
(MLX 4-bit)** as the local default, plus an **opt-in OpenRouter cloud engine** (008), both
behind one stable interface so the model can be swapped in one file (Principle V).

## Public interface

- `interface.LLMEngine` (Protocol) — the stable contract consumers depend on.
- `interface.LLMEngineError`.

## Dependencies

- **Engine package owned here (Principle V — function-local):** `mlx_lm` → `qwen_engine.py`.
  `qwen_engine.py` is the ONLY file in the repo that imports `mlx_lm`.
- **Cloud engine (008):** `openrouter_engine.py` is the ONLY file that talks to OpenRouter,
  over **stdlib `urllib`** (no new dependency). `openrouter_config.py` reads the model id from
  `~/.speakloop/openrouter.yaml` (`pyyaml`, already a dep); `openrouter_credentials.py` is a
  pure token resolver (env > file).
- Internal: `speakloop.installer` (model paths/manifest), `speakloop.config` (cloud paths).

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

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md); research: `doc/research_llm.md`.
