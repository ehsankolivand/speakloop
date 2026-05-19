"""Contract test for the LLM engine Protocol shape."""

from __future__ import annotations

import pytest

from speakloop.llm import LLMEngine, LLMEngineError

pytestmark = pytest.mark.contract


class StubLLMEngine:
    def __init__(self, response: str) -> None:
        self._r = response

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7):
        return self._r


def test_stub_satisfies_llm_protocol():
    engine: LLMEngine = StubLLMEngine("Hello, world.")
    out = engine.generate("sys", "user")
    assert out == "Hello, world."
    assert "<think>" not in out  # Qwen3-8B leak guard


def test_llm_engine_error_is_exception():
    assert issubclass(LLMEngineError, Exception)
