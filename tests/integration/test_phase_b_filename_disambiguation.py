"""T065 — second session same day same question → -2 suffix."""

from __future__ import annotations

import pytest

from speakloop.feedback.markdown_writer import next_available_path

pytestmark = pytest.mark.integration


def test_repeat_session_gets_disambiguated(tmp_path):
    p1 = next_available_path(tmp_path, "2026-05-18", "kotlin-coroutines-basics")
    p1.write_text("first")
    p2 = next_available_path(tmp_path, "2026-05-18", "kotlin-coroutines-basics")
    assert p2.name == "2026-05-18-kotlin-coroutines-basics-2.md"
    p2.write_text("second")
    assert p1.read_text() == "first"
    assert p2.read_text() == "second"
