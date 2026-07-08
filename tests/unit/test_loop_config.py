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


def test_effort_unset_by_default():
    c = loop_config.load()
    assert c.claude_fast_effort is None
    assert c.claude_strong_effort is None


def test_reads_effort_levels_normalized():
    _write("claude_fast_effort: LOW\nclaude_strong_effort: high\n")
    c = loop_config.load()
    assert c.claude_fast_effort == "low"  # normalized to lowercase
    assert c.claude_strong_effort == "high"


def test_invalid_effort_falls_back_to_unset():
    _write("claude_fast_effort: turbo\nclaude_strong_effort: 7\n")
    c = loop_config.load()
    assert c.claude_fast_effort is None  # unknown level → no flag emitted
    assert c.claude_strong_effort is None


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


# --- 017 P2: pronunciation trainer playback speed ---------------------------------------


def test_017_tts_speed_default_is_slower_than_one():
    # The learner reported the 1.0 cadence read too fast; the trainer default is slower.
    c = loop_config.load()
    assert c.pronunciation_tts_speed == loop_config.DEFAULT_PRONUNCIATION_TTS_SPEED
    assert 0.5 <= c.pronunciation_tts_speed < 1.0


def test_017_tts_speed_read_and_clamped():
    _write("pronunciation_tts_speed: 0.7\n")
    assert loop_config.load().pronunciation_tts_speed == 0.7
    _write("pronunciation_tts_speed: 5.0\n")  # absurd → clamped to the max band
    assert loop_config.load().pronunciation_tts_speed == loop_config.MAX_PRONUNCIATION_TTS_SPEED
    _write("pronunciation_tts_speed: 0.1\n")  # too slow → clamped to the floor
    assert loop_config.load().pronunciation_tts_speed == loop_config.MIN_PRONUNCIATION_TTS_SPEED


def test_017_tts_speed_invalid_falls_back():
    _write("pronunciation_tts_speed: fast\n")
    assert loop_config.load().pronunciation_tts_speed == loop_config.DEFAULT_PRONUNCIATION_TTS_SPEED


def test_017_teach_speed_is_a_step_slower_than_drill_speed():
    # The focused teaching beat is always slower than the drill cadence, never below the floor.
    assert loop_config.teach_speed(0.85) < 0.85
    assert loop_config.teach_speed(0.85) == 0.68
    assert loop_config.teach_speed(0.5) >= loop_config.MIN_PRONUNCIATION_TTS_SPEED


# --- 018: rescue-lines deck run cap ------------------------------------------------------


def test_018_deck_capacity_default_is_twenty():
    assert loop_config.load().deck_daily_capacity == 20


def test_018_deck_capacity_read_and_floored():
    _write("deck_daily_capacity: 8\n")
    assert loop_config.load().deck_daily_capacity == 8
    _write("deck_daily_capacity: 0\n")  # floored at 1
    assert loop_config.load().deck_daily_capacity == 1
    _write("deck_daily_capacity: lots\n")  # invalid → default
    assert loop_config.load().deck_daily_capacity == 20
