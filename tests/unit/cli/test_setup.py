"""T012 (015) — cli.setup: persist engine + engine-aware provisioning (no live engines)."""

from __future__ import annotations

import pytest
import typer

from speakloop import installer
from speakloop.cli import setup
from speakloop.config import loop_config

pytestmark = pytest.mark.unit


@pytest.fixture
def record_ensure(monkeypatch):
    """Record the phases passed to installer.ensure_models; download nothing."""
    phases: list[str] = []

    def _fake(phase, *, console=None, **kwargs):
        phases.append(phase)

    monkeypatch.setattr(installer, "ensure_models", _fake)
    return phases


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # Never touch the real claude binary from setup's readiness summary.
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.doctor_probe",
        lambda: {"installed": False, "binary": None, "logged_in": None},
    )


def test_setup_local_provisions_base_and_local_llm(record_ensure):
    setup.run(engine="local")
    assert record_ensure == ["B", "C"]
    assert loop_config.load().engine == "local"


@pytest.mark.parametrize("engine", ["openrouter", "claude"])
def test_setup_cloud_provisions_base_only(record_ensure, engine):
    setup.run(engine=engine)
    assert record_ensure == ["B"]  # the large local LLM is never fetched
    assert "C" not in record_ensure
    assert loop_config.load().engine == engine


def test_setup_no_download_skips_provisioning(record_ensure):
    setup.run(engine="openrouter", no_download=True)
    assert record_ensure == []
    assert loop_config.load().engine == "openrouter"


def test_setup_invalid_engine_exits_2_without_persisting(record_ensure):
    with pytest.raises(typer.Exit) as exc:
        setup.run(engine="gpt")
    assert exc.value.exit_code == 2
    assert record_ensure == []
    assert loop_config.load().engine == "local"  # unchanged default


def test_setup_non_interactive_keeps_current(record_ensure, monkeypatch):
    loop_config.save_engine("claude")
    # No --engine and stdin is not a tty under pytest → keep current, no prompt.
    setup.run(engine=None, no_download=True, input_fn=_boom)
    assert loop_config.load().engine == "claude"


def test_setup_interactive_prompt_selects_engine(record_ensure, monkeypatch):
    class _TTY:
        def isatty(self):
            return True

    monkeypatch.setattr("sys.stdin", _TTY())
    # "2" → second VALID_ENGINES entry → openrouter.
    setup.run(engine=None, no_download=True, input_fn=lambda prompt: "2")
    assert loop_config.load().engine == "openrouter"


def _boom(prompt):
    raise AssertionError("input_fn must not be called in the non-interactive path")
