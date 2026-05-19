"""
LLM module public interface — STABLE contract.

Constitution Principle V (Swappable Engines): only files inside
`src/speakloop/llm/` may import engine-specific packages such as
`mlx_lm`, `llama_cpp`, or `ollama`. Every other module imports from
`speakloop.llm` and depends only on the `LLMEngine` Protocol below.

The v1 LLM is used only for offline (non-streaming) generation of the
feedback report. There is NO real-time conversational loop. Streaming
support is therefore not part of the v1 contract; if a future engine
swap wants to stream tokens to disk while writing, that is a v2 concern.

Swapping Qwen3.5-9B for Llama 3.1 8B (or any future engine) MUST
require changes in exactly one file (`llm/<engine>_engine.py`) plus, at
most, an entry in `installer/manifest.py`. The Protocol below MUST NOT
change shape.
"""

from __future__ import annotations

from typing import Protocol


class LLMEngine(Protocol):
    """A local LLM that produces text from a system + user prompt."""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a single response.

        The implementation MUST honour the offline-only constraint —
        no network calls. The implementation MUST also ensure that any
        engine-specific "thinking" mode is disabled so the returned
        string never contains ``<think>...</think>`` blocks (this is
        the documented Qwen3-8B failure mode; Qwen3.5 small series
        disables thinking by default — verify before each engine swap).

        Args:
            system_prompt: The role / instructions block.
            user_prompt: The user-side content (typically the three
                transcripts plus the metrics block).
            max_tokens: Hard cap on output length.
            temperature: Sampling temperature.

        Returns:
            The model's response text, with any tokenizer-internal
            artifacts (BOS/EOS markers, chat template residue) already
            stripped by the wrapper.

        Raises:
            LLMEngineError: if generation fails for any reason.
        """
        ...


class LLMEngineError(Exception):
    """Single public error class for all LLM failures."""
