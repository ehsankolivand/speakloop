"""Integration: an absent/failing Claude Code engine degrades to analysis_pending (011).

No real `claude` binary is ever spawned — the engine's runner is replaced with one
that raises FileNotFoundError (the "not installed" path)."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from speakloop.asr import Transcript
from speakloop.llm.interface import LLMEngineError

pytestmark = pytest.mark.integration


@pytest.fixture
def absent_claude_analyzer(monkeypatch):
    """Build the claude grammar analyzer with a runner that simulates an absent CLI."""
    from speakloop.cli import practice as _practice
    from speakloop.llm import claude_code_engine

    real_cls = claude_code_engine.ClaudeCodeEngine

    def _absent_runner(argv, stdin, timeout, env):
        raise FileNotFoundError(2, "No such file or directory: 'claude'")

    def _factory(*, model, **_kw):
        return real_cls(model=model, runner=_absent_runner)

    # The builder imports ClaudeCodeEngine function-locally → picks up this patch.
    monkeypatch.setattr(claude_code_engine, "ClaudeCodeEngine", _factory)
    # Don't touch the real ~/.speakloop prompt files.
    monkeypatch.setattr(
        "speakloop.feedback.cloud_prompt.load_cloud_prompt",
        lambda: ("GRAMMAR PROMPT", Path("/tmp/p.txt")),
    )
    monkeypatch.setattr(
        "speakloop.feedback.cloud_prompt.load_coach_prompt",
        lambda: ("COACH PROMPT", Path("/tmp/c.txt")),
    )
    return _practice._build_claude_grammar_analyzer(Console())


def test_builder_returns_non_none_with_runners(absent_claude_analyzer):
    # Always a real analyzer so the session degrades to analysis_pending rather than the
    # "no Phase-C model installed" path — and never auto-falls back to local.
    assert absent_claude_analyzer.runner is not None
    assert absent_claude_analyzer.coach is not None
    assert absent_claude_analyzer.runners is not None


def test_analysis_call_raises_llm_engine_error(absent_claude_analyzer):
    grammar_analyzer = absent_claude_analyzer.runner
    with pytest.raises(LLMEngineError):
        grammar_analyzer([Transcript(text="I has two apple.")])


def test_coordinator_contract_sets_analysis_pending(absent_claude_analyzer):
    """Replicate the coordinator's degradation clause: a raising analyzer → pending."""
    grammar_analyzer = absent_claude_analyzer.runner
    analysis_pending = False
    phase = "B"
    try:  # mirrors sessions/coordinator.py: try grammar_analyzer(...) except Exception
        grammar_analyzer([Transcript(text="I has two apple.")])
        phase = "C"
    except Exception:  # noqa: BLE001 — exactly what the coordinator does
        analysis_pending = True
    assert analysis_pending is True
    assert phase == "B"  # the deterministic Phase-B report is still written + resumable
