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

- `interface.py` — `LLMEngine` Protocol + `LLMEngineError`.
- `qwen_engine.py` — `QwenEngine`; the only `import mlx_lm`; lazy load + sampling
  (`make_sampler`, `generate`).

## Common modification patterns

- **Swap the LLM**: implement `LLMEngine` in a new `*_engine.py`, keep its package import
  function-local, point the model id at the manifest entry. Touch no other module.
- **Change the model build**: edit the manifest entry in `installer/manifest.py`, not here.

## Traps

- **The model intentionally diverges from research.** `doc/research_llm.md` chose Qwen3.5-9B,
  but that HF repo is a vision-language model incompatible with `mlx_lm.load()`; the code ships
  `Qwen3-8B-4bit` (`installer/manifest.py:56-65`). Do not "fix" it back to the research choice.
- **Thinking mode MUST stay disabled** — the Qwen3-8B `<think>` leak guard (research_llm.md).

## Never do

- Import `mlx_lm` anywhere but `qwen_engine.py`, or at module top level (Principle V/VIII).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md); research: `doc/research_llm.md`.
