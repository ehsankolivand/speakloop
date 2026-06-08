"""008: OpenRouter model-id resolution from ~/.speakloop/openrouter.yaml.

Absent file / key, and malformed YAML, all degrade to the pinned default
(SC-004 resolver behavior). pyyaml is already a project dependency.
"""

from __future__ import annotations

import pytest

from speakloop.llm import openrouter_config as cfg

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    return tmp_path


def _write(home, text: str):
    (home / "openrouter.yaml").write_text(text, encoding="utf-8")


def test_absent_file_returns_default(_home):
    assert cfg.resolve_model() == "qwen/qwen3.7-max"


def test_model_key_returned(_home):
    _write(_home, "model: anthropic/claude-3.5-sonnet\n")
    assert cfg.resolve_model() == "anthropic/claude-3.5-sonnet"


def test_model_value_stripped(_home):
    _write(_home, "model:   spaced/model   \n")
    assert cfg.resolve_model() == "spaced/model"


def test_missing_key_returns_default(_home):
    _write(_home, "other: 1\n")
    assert cfg.resolve_model() == "qwen/qwen3.7-max"


def test_empty_model_returns_default(_home):
    _write(_home, "model: ''\n")
    assert cfg.resolve_model() == "qwen/qwen3.7-max"


def test_malformed_yaml_returns_default(_home):
    _write(_home, "model: [unclosed\n:::not yaml")
    assert cfg.resolve_model() == "qwen/qwen3.7-max"


def test_non_mapping_yaml_returns_default(_home):
    _write(_home, "- just\n- a\n- list\n")
    assert cfg.resolve_model() == "qwen/qwen3.7-max"


def test_edit_changes_resolution(_home):
    assert cfg.resolve_model() == "qwen/qwen3.7-max"
    _write(_home, "model: openai/gpt-4o-mini\n")
    assert cfg.resolve_model() == "openai/gpt-4o-mini"
