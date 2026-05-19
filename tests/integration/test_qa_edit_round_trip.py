"""T100 — user edits qa.yaml, new entry appears on next load."""

from __future__ import annotations

import pytest

from speakloop.content import load

pytestmark = pytest.mark.integration


INITIAL = """schema_version: 1
questions:
  - id: q-one
    question: First?
    ideal_answer: First.
"""


def test_round_trip_pickup_new_entry(tmp_path):
    qa = tmp_path / "qa.yaml"
    qa.write_text(INITIAL)
    initial = load(qa)
    assert len(initial.questions) == 1

    # User edits the file in their editor — append a new entry.
    qa.write_text(INITIAL + "  - id: q-two\n    question: Second?\n    ideal_answer: Second.\n")

    reloaded = load(qa)
    assert [q.id for q in reloaded.questions] == ["q-one", "q-two"]
