"""T021 (015) — `speakloop questions` validate / template / where."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app

pytestmark = pytest.mark.unit

runner = CliRunner()


def test_validate_ok(qa_fixture):
    result = runner.invoke(app, ["questions", "validate", str(qa_fixture("valid.yaml"))])
    assert result.exit_code == 0
    assert "OK" in result.stdout
    assert "2 question" in result.stdout


def test_validate_missing_field_names_entry_and_field(qa_fixture):
    result = runner.invoke(app, ["questions", "validate", str(qa_fixture("missing-field.yaml"))])
    assert result.exit_code == 1
    assert "no-ideal-answer" in result.stdout  # the offending entry id
    assert "ideal_answer" in result.stdout  # the offending field


def test_validate_syntax_error_reports_and_exits_nonzero(qa_fixture):
    result = runner.invoke(app, ["questions", "validate", str(qa_fixture("invalid-syntax.yaml"))])
    assert result.exit_code == 1
    assert "Invalid question file" in result.stdout


def test_validate_missing_file_exits_nonzero(tmp_path):
    result = runner.invoke(app, ["questions", "validate", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 1


def test_template_round_trips_through_loader(tmp_path):
    result = runner.invoke(app, ["questions", "template"])
    assert result.exit_code == 0
    out = tmp_path / "out.yaml"
    out.write_text(result.stdout, encoding="utf-8")
    from speakloop.content import load

    qa = load(out)
    assert len(qa.questions) >= 2


def test_where_shows_precedence_and_active(monkeypatch, qa_fixture):
    monkeypatch.setenv("SPEAKLOOP_QA_FILE", str(qa_fixture("valid.yaml")))
    result = runner.invoke(app, ["questions", "where"])
    assert result.exit_code == 0
    assert "precedence" in result.stdout.lower()
    assert "Active file" in result.stdout


def test_questions_help_lists_subcommands():
    result = runner.invoke(app, ["questions", "--help"])
    assert result.exit_code == 0
    for sub in ("validate", "template", "where"):
        assert sub in result.stdout
