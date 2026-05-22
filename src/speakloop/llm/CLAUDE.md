# llm

## Purpose

LLM engine wrapper for educational grammar/coherence feedback [Phase C]. Ships **Qwen3-8B
(MLX 4-bit)** behind a stable interface so the model can be swapped in one file (Principle V).

## Public interface

- `interface.LLMEngine` (Protocol) — the stable contract consumers depend on.
- `interface.LLMEngineError`.

## Dependencies

- **Engine package owned here (Principle V — function-local):** `mlx_lm` → `qwen_engine.py`
  (lines 47, 78, 79). `qwen_engine.py` is the ONLY file in the repo that imports `mlx_lm`.
- Internal: `speakloop.installer` (model paths/manifest).

## Consumers

`cli`, `feedback`.

## File map

- `interface.py` — `LLMEngine` Protocol + `LLMEngineError`. `generate(...)` takes an
  additive optional `retry` flag (intent only — the wrapper owns the engine config).
- `qwen_engine.py` — `QwenEngine`; the only `import mlx_lm`; lazy load + the full
  generation config (`make_sampler` temp 0.7/top_p 0.8/top_k 20/min_p 0 +
  `make_logits_processors` repetition_penalty 1.05/context 40 + defensive `<|im_end|>`
  truncation). `retry=True` raises repetition_penalty→1.15 and lowers temp by 0.1
  for the analyzer's one bounded regenerate (006).

## Common modification patterns

- **Swap the LLM**: implement `LLMEngine` in a new `*_engine.py`, keep its package import
  function-local, point the model id at the manifest entry. Touch no other module.
- **Change the model build**: edit the manifest entry in `installer/manifest.py`, not here.

## Traps

- **The model intentionally diverges from research.** `doc/research_llm.md` chose Qwen3.5-9B,
  but that HF repo is a vision-language model incompatible with `mlx_lm.load()`; the code ships
  `Qwen3-8B-4bit` (`installer/manifest.py:56-65`). Do not "fix" it back to the research choice.
- **Thinking mode MUST stay disabled** — the Qwen3-8B `<think>` leak guard (research_llm.md).
- **All generation config lives HERE, not at the call site** (Principle V; 006). The analyzer
  passes intent only (`retry`); it never sets temperature/repetition_penalty/stop.
- **mlx-lm's generate has no `stop=` parameter** — the defensive EOS (`<|im_end|>`) is applied
  by truncating in `_strip_artefacts`, not by a generate kwarg. Don't add an unsupported kwarg.
- **Stay 4-bit** — 8-bit is out of scope (Decision 2); doubling the download/RAM is the wrong
  trade for the target user (Constitution VI/VII).

## Never do

- Import `mlx_lm` anywhere but `qwen_engine.py`, or at module top level (Principle V/VIII).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md); research: `doc/research_llm.md`.
