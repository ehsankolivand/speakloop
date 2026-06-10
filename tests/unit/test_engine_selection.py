"""Unit tests for engine selection precedence (011): --engine / --cloud / config / default."""

from __future__ import annotations

import pytest

from speakloop.cli.practice import EngineSelectionError, resolve_engine_choice
from speakloop.config.loop_config import LoopConfig

pytestmark = pytest.mark.unit


@pytest.fixture
def config_engine(monkeypatch):
    """Set the loop-config default engine that resolve_engine_choice falls back to."""

    def _set(value: str):
        monkeypatch.setattr(
            "speakloop.config.loop_config.load", lambda: LoopConfig(engine=value)
        )

    return _set


@pytest.mark.parametrize("flag", ["local", "openrouter", "claude"])
def test_explicit_flag_wins_over_config(config_engine, flag):
    config_engine("claude")  # config says claude, but the explicit flag must win
    assert resolve_engine_choice(flag, False) == flag


def test_cloud_is_openrouter_alias(config_engine):
    config_engine("local")
    assert resolve_engine_choice(None, True) == "openrouter"


def test_engine_openrouter_with_cloud_is_allowed(config_engine):
    config_engine("local")
    assert resolve_engine_choice("openrouter", True) == "openrouter"


def test_config_default_used_when_no_flag(config_engine):
    config_engine("claude")
    assert resolve_engine_choice(None, False) == "claude"


def test_builtin_default_is_local(config_engine):
    config_engine("local")  # the LoopConfig default
    assert resolve_engine_choice(None, False) == "local"


def test_case_insensitive_and_trimmed(config_engine):
    config_engine("local")
    assert resolve_engine_choice("  Claude ", False) == "claude"


def test_unknown_engine_errors(config_engine):
    config_engine("local")
    with pytest.raises(EngineSelectionError):
        resolve_engine_choice("gpt-5", False)


@pytest.mark.parametrize("flag", ["local", "claude"])
def test_conflicting_engine_and_cloud_errors(config_engine, flag):
    config_engine("local")
    with pytest.raises(EngineSelectionError):
        resolve_engine_choice(flag, True)
