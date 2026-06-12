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


def test_validate_no_path_uses_resolved_active_file(monkeypatch, qa_fixture):
    # FR-017: no PATH → validate the precedence-resolved active file.
    monkeypatch.setenv("SPEAKLOOP_QA_FILE", str(qa_fixture("valid.yaml")))
    result = runner.invoke(app, ["questions", "validate"])
    assert result.exit_code == 0
    assert "2 question" in result.stdout


def test_validate_no_path_no_file_found(monkeypatch):
    monkeypatch.setattr("speakloop.config.paths.resolve_qa_file", lambda: None)
    result = runner.invoke(app, ["questions", "validate"])
    assert result.exit_code == 1
    assert "No question file found" in result.stdout


def test_where_no_active_file(monkeypatch):
    # FR-018 / Acceptance Scenario 4: when nothing resolves, say so + how to add one.
    monkeypatch.setattr("speakloop.config.paths.resolve_qa_file", lambda: None)
    result = runner.invoke(app, ["questions", "where"])
    assert result.exit_code == 0
    assert "none found" in result.stdout.lower()


def test_validate_reports_non_fatal_warnings(tmp_path):
    # FR-017: a file that loads but has a warning (unknown type) → exit 0 + warning shown.
    f = tmp_path / "warn.yaml"
    f.write_text(
        "schema_version: 1\n"
        "questions:\n"
        "  - id: q1\n"
        "    question: What is a stack?\n"
        "    ideal_answer: A LIFO collection.\n"
        "    type: bogus\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["questions", "validate", str(f)])
    assert result.exit_code == 0
    assert "warning" in result.stdout.lower()
