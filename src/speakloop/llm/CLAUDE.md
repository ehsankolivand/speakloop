# llm

LLM engine wrapper (Phase C).

**Public surface**: `interface.LLMEngine` (Protocol), `interface.LLMEngineError`.

**Engine wrapper**: `qwen_engine.QwenEngine` — the ONLY file in the repo allowed
to `import mlx_lm` (Constitution Principle V).

Thinking mode MUST be disabled (Qwen3-8B `<think>` leak guard — research_llm.md).
