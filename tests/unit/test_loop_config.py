"""Unit tests for loop-config parsing — the 011 engine/model/timeout additions."""

from __future__ import annotations

import pytest

from speakloop.config import loop_config, paths

pytestmark = pytest.mark.unit


def _write(text: str) -> None:
    # The autouse `_isolate_loop_config` fixture points loop_config_path at a fresh
    # temp file; write the config there so load() reads it (never the real ~/.speakloop).
    p = paths.loop_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_defaults_when_absent():
    c = loop_config.load()
    assert c.engine == "local"
    assert c.claude_fast_model == "haiku"
    assert c.claude_strong_model == "sonnet"
    assert c.claude_timeout_seconds == 240


def test_reads_claude_keys():
    _write(
        "engine: claude\n"
        "claude_fast_model: sonnet\n"
        "claude_strong_model: claude-opus-4-8\n"
        "claude_timeout_seconds: 300\n"
    )
    c = loop_config.load()
    assert c.engine == "claude"
    assert c.claude_fast_model == "sonnet"
    assert c.claude_strong_model == "claude-opus-4-8"
    assert c.claude_timeout_seconds == 300


def test_invalid_engine_falls_back_to_local():
    _write("engine: gpt-5\n")
    assert loop_config.load().engine == "local"


def test_invalid_timeout_falls_back_to_default():
    _write("claude_timeout_seconds: not-a-number\n")
    assert loop_config.load().claude_timeout_seconds == 240


def test_blank_models_fall_back_to_defaults():
    _write("claude_fast_model: ''\nclaude_strong_model: '   '\n")
    c = loop_config.load()
    assert c.claude_fast_model == "haiku"
    assert c.claude_strong_model == "sonnet"


# --- 012: autoplay toggle + analysis concurrency -----------------------------


def test_012_defaults_when_absent():
    c = loop_config.load()
    assert c.autoplay_ideal_answer is True
    assert c.analysis_concurrency == 3


def test_012_reads_autoplay_and_concurrency():
    _write("autoplay_ideal_answer: false\nanalysis_concurrency: 5\n")
    c = loop_config.load()
    assert c.autoplay_ideal_answer is False
    assert c.analysis_concurrency == 5


def test_012_concurrency_clamped_to_at_least_one():
    _write("analysis_concurrency: 0\n")
    assert loop_config.load().analysis_concurrency == 1


def test_012_invalid_values_fall_back():
    _write("autoplay_ideal_answer: maybe\nanalysis_concurrency: lots\n")
    c = loop_config.load()
    assert c.autoplay_ideal_answer is True
    assert c.analysis_concurrency == 3
