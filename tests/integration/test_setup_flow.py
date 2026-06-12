"""T014 (015) — fresh-clone setup flow: persist engine + engine-aware provisioning."""

from __future__ import annotations

import pytest

from speakloop import installer
from speakloop.cli import setup
from speakloop.cli.practice import resolve_engine_choice
from speakloop.config import loop_config

pytestmark = pytest.mark.integration


@pytest.fixture
def record_ensure(monkeypatch):
    phases: list[str] = []
    monkeypatch.setattr(installer, "ensure_models", lambda phase, **k: phases.append(phase))
    return phases


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.doctor_probe",
        lambda: {"installed": False, "binary": None, "logged_in": None},
    )


def test_setup_openrouter_never_fetches_local_llm(record_ensure):
    setup.run(engine="openrouter")
    assert "C" not in record_ensure
    assert record_ensure == ["B"]
    # Persisted, and visible to the no-flag engine resolution.
    assert loop_config.load().engine == "openrouter"
    assert resolve_engine_choice(None, False) == "openrouter"


def test_setup_local_fetches_local_llm(record_ensure):
    setup.run(engine="local")
    assert record_ensure == ["B", "C"]
    assert resolve_engine_choice(None, False) == "local"


def test_explicit_flag_overrides_persisted_default(record_ensure):
    setup.run(engine="openrouter", no_download=True)
    # The persisted default is openrouter, but an explicit per-run flag wins...
    assert resolve_engine_choice("local", False) == "local"
    # ...without changing what is persisted.
    assert loop_config.load().engine == "openrouter"
