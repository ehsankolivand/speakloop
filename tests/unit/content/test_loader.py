"""T037 — loader behaviour (FR-029, FR-030)."""

from __future__ import annotations

import pytest

from speakloop.content import QALoadError, load

pytestmark = pytest.mark.unit


def test_load_valid_returns_two_questions(qa_fixture):
    qa = load(qa_fixture("valid.yaml"))
    assert len(qa.questions) == 2
    assert qa.questions[0].id == "kotlin-coroutines-basics"


def test_invalid_syntax_includes_path_and_line(qa_fixture):
    path = qa_fixture("invalid-syntax.yaml")
    with pytest.raises(QALoadError) as exc:
        load(path)
    msg = str(exc.value)
    assert str(path) in msg
    # Line number prefix `path:line:` should be present (FR-029).
    assert ":" in msg
    assert any(part.isdigit() for part in msg.replace(":", " ").split())


def test_missing_field_names_entry_id_and_field(qa_fixture):
    with pytest.raises(QALoadError) as exc:
        load(qa_fixture("missing-field.yaml"))
    msg = str(exc.value)
    assert "no-ideal-answer" in msg
    assert "ideal_answer" in msg
