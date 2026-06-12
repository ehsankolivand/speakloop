"""T010 (015) — installer.engine_needs_local_llm provisioning predicate."""

from __future__ import annotations

import pytest

from speakloop import installer

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "engine,listen_only,expected",
    [
        ("local", False, True),  # only this combination needs the local LLM
        ("local", True, False),  # listen-only never needs ASR or the LLM
        ("openrouter", False, False),
        ("openrouter", True, False),
        ("claude", False, False),
        ("claude", True, False),
    ],
)
def test_engine_needs_local_llm(engine, listen_only, expected):
    assert installer.engine_needs_local_llm(engine, listen_only=listen_only) is expected


def test_exported_in_all():
    assert "engine_needs_local_llm" in installer.__all__
