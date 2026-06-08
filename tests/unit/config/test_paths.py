"""008: OpenRouter cloud path accessors in config/paths.py.

Pure path resolution under SPEAKLOOP_HOME — no file reads (the config leaf is
stdlib-only; the YAML is read in llm/openrouter_config.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.config import paths

pytestmark = pytest.mark.unit


def test_token_path_default(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    assert paths.openrouter_token_path() == tmp_path / "openrouter_token"


def test_config_path_default(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    assert paths.openrouter_config_path() == tmp_path / "openrouter.yaml"


def test_prompt_path_default(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    assert paths.openrouter_prompt_path() == tmp_path / "openrouter_prompt.txt"


def test_speakloop_home_override_honored(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "custom"))
    assert paths.openrouter_token_path().parent == tmp_path / "custom"
    assert paths.openrouter_config_path().parent == tmp_path / "custom"
    assert paths.openrouter_prompt_path().parent == tmp_path / "custom"


def test_accessors_are_pure_no_io(monkeypatch, tmp_path):
    # Calling the accessors must not create any file/dir (PATHS only).
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    _ = (
        paths.openrouter_token_path(),
        paths.openrouter_config_path(),
        paths.openrouter_prompt_path(),
    )
    assert list(Path(tmp_path).iterdir()) == []
