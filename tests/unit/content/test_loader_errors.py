"""T101 — loader error formatting (FR-029, FR-030)."""

from __future__ import annotations

import re

import pytest

from speakloop.content import QALoadError, load

pytestmark = pytest.mark.unit


def test_invalid_syntax_format_includes_path_colon_line_colon(qa_fixture):
    path = qa_fixture("invalid-syntax.yaml")
    with pytest.raises(QALoadError) as exc:
        load(path)
    msg = str(exc.value)
    # FR-029: <path>:<line>: prefix.
    assert re.search(rf"^{re.escape(str(path))}:\d+:", msg), msg
    assert "Hint" in msg or "fix" in msg.lower()


def test_missing_ideal_answer_message_names_entry_and_field(qa_fixture):
    with pytest.raises(QALoadError) as exc:
        load(qa_fixture("missing-field.yaml"))
    msg = str(exc.value)
    assert "no-ideal-answer" in msg
    assert "ideal_answer" in msg
