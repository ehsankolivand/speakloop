"""T014 (015) — fresh-clone setup flow: persist engine + engine-aware provisioning."""

from __future__ import annotations

import pytest

from typer.testing import CliRunner

from speakloop import installer
from speakloop.cli import setup
from speakloop.cli.main import app
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


def test_no_home_files_created_except_loop_yaml(monkeypatch, tmp_path):
    """SC-007 / FR-005 / FR-019: template/validate/where write nothing to home; setup
    --no-download writes only loop.yaml."""
    home = tmp_path / "home"
    monkeypatch.setenv("SPEAKLOOP_HOME", str(home))
    # Let loop.yaml resolve UNDER home (override the autouse loop-config isolation) so we can
    # assert it is the only thing written there.
    monkeypatch.setattr("speakloop.config.paths.loop_config_path", lambda: home / "loop.yaml")
    runner = CliRunner()

    # template + validate + where must not create anything in home.
    tmpl = runner.invoke(app, ["questions", "template"])
    assert tmpl.exit_code == 0
    qa = tmp_path / "mine.yaml"
    qa.write_text(tmpl.stdout, encoding="utf-8")
    assert runner.invoke(app, ["questions", "validate", str(qa)]).exit_code == 0
    assert runner.invoke(app, ["questions", "where"]).exit_code == 0
    assert not home.exists()  # nothing has touched home yet

    # setup --no-download persists ONLY loop.yaml into home.
    assert runner.invoke(app, ["setup", "--engine", "openrouter", "--no-download"]).exit_code == 0
    assert sorted(p.name for p in home.iterdir()) == ["loop.yaml"]
