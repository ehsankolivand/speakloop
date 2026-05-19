"""Contract test for the CLI surface (FR-018)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app

pytestmark = pytest.mark.contract

runner = CliRunner()


def test_help_works_without_models():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "practice" in out
    assert "doctor" in out
    assert "trends" in out
    assert "--qa-file" in out
    assert "--models-dir" in out


def test_version_works_without_models():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "speakloop" in result.stdout
