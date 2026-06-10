"""Question `type` field tests (010-interview-loop, T082)."""

from __future__ import annotations

import pytest

from speakloop.content import schema

pytestmark = pytest.mark.unit


def _doc(questions):
    return {"schema_version": 1, "questions": questions}


def test_absent_type_defaults_to_definition():
    qa = schema.parse(_doc([{"id": "q1", "question": "Q", "ideal_answer": "A"}]))
    assert qa.questions[0].type == "definition"
    assert qa.warnings == []


def test_valid_types_parsed():
    qa = schema.parse(_doc([
        {"id": "b", "question": "Q", "ideal_answer": "A", "type": "behavioral"},
        {"id": "h", "question": "Q", "ideal_answer": "A", "type": "hypothetical"},
    ]))
    assert [q.type for q in qa.questions] == ["behavioral", "hypothetical"]


def test_unknown_type_warns_and_defaults():
    qa = schema.parse(_doc([{"id": "q", "question": "Q", "ideal_answer": "A", "type": "trivia"}]))
    assert qa.questions[0].type == "definition"
    assert any("unknown type" in w for w in qa.warnings)


def test_schema_version_unchanged():
    # adding `type` must not require a question-file schema_version bump
    qa = schema.parse(_doc([{"id": "q", "question": "Q", "ideal_answer": "A", "type": "behavioral"}]))
    assert qa.schema_version == 1
