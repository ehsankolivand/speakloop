"""Unit tests for Claude Code model tiering (011 P2) — fake runners, no real CLI."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
from rich.console import Console

from speakloop.asr import Transcript
from speakloop.cli import practice as _practice
from speakloop.config.loop_config import LoopConfig

pytestmark = pytest.mark.unit


def _models_used(runner):
    return [c.argv[c.argv.index("--model") + 1] for c in runner.calls]


def _call(fn, *args):
    # We only care WHICH engine was invoked (the runner records the --model argv);
    # downstream parse success is irrelevant, so swallow any analysis-side error.
    with contextlib.suppress(Exception):
        fn(*args)


def test_tiering_routes_cheap_calls_to_fast_and_rest_to_strong(fake_claude):
    from speakloop.llm.claude_code_engine import ClaudeCodeEngine

    fast_runner = fake_claude.Runner(fake_claude.success("{}"))
    strong_runner = fake_claude.Runner(fake_claude.success("{}"))
    fast = ClaudeCodeEngine(model="haiku", runner=fast_runner)
    strong = ClaudeCodeEngine(model="sonnet", runner=strong_runner)
    runners = _practice._build_runners(strong, fast_engine=fast)

    ts = [Transcript(text="I has two apple.")]

    # Cheap / mechanical calls → fast model only.
    _call(runners.mishearing, "I has two apple.")
    _call(runners.drill, "subject-verb agreement")
    assert fast_runner.calls, "mishearing/drill should hit the fast engine"
    assert all(m == "haiku" for m in _models_used(fast_runner))
    assert strong_runner.calls == [], "cheap calls must not touch the strong engine"

    n_fast = len(fast_runner.calls)

    # Reasoning-heavy calls → strong model only.
    _call(runners.followups, "Explain X", ts)
    _call(runners.keypoints, "Explain X", "ideal answer", "technical")
    _call(runners.coverage, [], ts, "ideal answer", 1)
    _call(runners.consistency, "artifact text", "ideal answer")
    assert strong_runner.calls, "reasoning calls should hit the strong engine"
    assert all(m == "sonnet" for m in _models_used(strong_runner))
    assert len(fast_runner.calls) == n_fast, "reasoning calls must not touch the fast engine"


def test_default_runners_use_a_single_engine(fake_claude):
    """Without fast_engine (local/openrouter path) both tiers share one engine."""
    from speakloop.llm.claude_code_engine import ClaudeCodeEngine

    runner = fake_claude.Runner(fake_claude.success("{}"))
    engine = ClaudeCodeEngine(model="solo", runner=runner)
    runners = _practice._build_runners(engine)  # no fast_engine

    _call(runners.mishearing, "text")
    _call(runners.followups, "q", [Transcript(text="a")])
    assert runner.calls
    assert all(m == "solo" for m in _models_used(runner))  # one model for everything


def test_config_overrides_tier_models(monkeypatch, fake_claude):
    from speakloop.llm import claude_code_engine

    monkeypatch.setattr(
        "speakloop.config.loop_config.load",
        lambda: LoopConfig(
            engine="claude", claude_fast_model="myfast", claude_strong_model="mystrong"
        ),
    )
    constructed: list[str] = []
    real_cls = claude_code_engine.ClaudeCodeEngine

    def _factory(*, model, **_kw):
        constructed.append(model)
        return real_cls(model=model, runner=fake_claude.Runner(fake_claude.success("{}")))

    monkeypatch.setattr(claude_code_engine, "ClaudeCodeEngine", _factory)
    monkeypatch.setattr(
        "speakloop.feedback.cloud_prompt.load_cloud_prompt", lambda: ("P", Path("/tmp/p"))
    )
    monkeypatch.setattr(
        "speakloop.feedback.cloud_prompt.load_coach_prompt", lambda: ("C", Path("/tmp/c"))
    )

    _practice._build_claude_grammar_analyzer(Console())
    assert "myfast" in constructed
    assert "mystrong" in constructed


def test_tier_map_matches_runner_wiring():
    # The documented constant is the single source of truth for the assignment.
    assert _practice.CLAUDE_TIER_MAP["fast"] == ("mishearing", "drill")
    assert "coverage" in _practice.CLAUDE_TIER_MAP["strong"]
    assert "grammar" in _practice.CLAUDE_TIER_MAP["strong"]
