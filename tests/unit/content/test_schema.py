"""T038 — Question validation rules."""

from __future__ import annotations

import pytest

from speakloop.content.schema import QASchemaError, parse

pytestmark = pytest.mark.unit


def _doc(**overrides):
    base = {
        "schema_version": 1,
        "questions": [
            {
                "id": "valid-id",
                "question": "What is X?",
                "ideal_answer": "X is Y.",
            }
        ],
    }
    base["questions"][0].update(overrides)
    return base


def test_duplicate_id_rejected():
    doc = {
        "schema_version": 1,
        "questions": [
            {"id": "x", "question": "q1", "ideal_answer": "a1"},
            {"id": "x", "question": "q2", "ideal_answer": "a2"},
        ],
    }
    with pytest.raises(QASchemaError, match="duplicate"):
        parse(doc)


def test_long_id_rejected():
    doc = _doc(id="a" * 41)
    with pytest.raises(QASchemaError, match="exceeds 40"):
        parse(doc)


def test_empty_question_after_strip_rejected():
    doc = _doc(question="   \n  ")
    with pytest.raises(QASchemaError, match="missing or empty"):
        parse(doc)


def test_unknown_key_becomes_warning():
    doc = _doc(silly_key="ignored")
    qa = parse(doc)
    assert any("silly_key" in w for w in qa.warnings)


def test_non_kebab_id_rejected():
    doc = _doc(id="HasCapitals")
    with pytest.raises(QASchemaError, match="kebab-case"):
        parse(doc)
