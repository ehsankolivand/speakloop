"""
LLM module public interface — STABLE contract.

Constitution Principle V: only files inside `src/speakloop/llm/` may
import engine-specific packages such as `mlx_lm`. Every other module
imports from `speakloop.llm` and depends only on the `LLMEngine`
Protocol below.
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
        retry: bool = False,
    ) -> str:
        """Generate text. ``retry=True`` signals a bounded regenerate after a
        repetition loop / truncation: the engine wrapper internally strengthens
        anti-repetition (the call site passes intent only, never engine config —
        Principle V). All other generation config is owned by the wrapper."""
        ...


class LLMEngineError(Exception):
    """Single public error class for all LLM failures."""
