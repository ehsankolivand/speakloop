"""T020 (015) — the canonical question template loads + validates unedited."""

from __future__ import annotations

import pytest

from speakloop.content import load
from speakloop.content.template import template_text

pytestmark = pytest.mark.unit


def test_template_loads_and_validates(tmp_path):
    f = tmp_path / "qa.yaml"
    f.write_text(template_text(), encoding="utf-8")
    qa = load(f)
    assert qa.schema_version == 1
    assert len(qa.questions) >= 2
    # Spans the three question types so the template doubles as schema documentation.
    types = {q.type for q in qa.questions}
    assert {"definition", "behavioral", "hypothetical"} <= types
    # A clean template produces no validation warnings.
    assert qa.warnings == []


def test_template_ids_are_unique_and_kebab(tmp_path):
    f = tmp_path / "qa.yaml"
    f.write_text(template_text(), encoding="utf-8")
    qa = load(f)
    ids = [q.id for q in qa.questions]
    assert len(ids) == len(set(ids))
    for qid in ids:
        assert qid == qid.lower()
        assert " " not in qid
