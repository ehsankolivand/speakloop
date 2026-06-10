"""T012 — engines declare their parallel-safety capability (012, FR-026)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_claude_engine_is_parallel_safe():
    from speakloop.llm.claude_code_engine import ClaudeCodeEngine

    assert ClaudeCodeEngine.parallel_safe is True


def test_openrouter_engine_is_parallel_safe():
    from speakloop.llm.openrouter_engine import OpenRouterEngine

    assert OpenRouterEngine.parallel_safe is True


def test_qwen_engine_is_not_parallel_safe():
    from speakloop.llm.qwen_engine import QwenEngine

    assert QwenEngine.parallel_safe is False
