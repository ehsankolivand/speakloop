"""009: cloud coaching prompt loader — seed-if-missing, read-verbatim, and
separate from BOTH the strict grammar cloud prompt and the local _SYSTEM_PROMPT.

Parallel to tests/unit/feedback/test_cloud_prompt.py (the grammar cloud prompt)."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.config import paths
from speakloop.feedback import cloud_prompt

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    return tmp_path


def test_seeds_coach_default_when_missing(_home):
    target = paths.openrouter_coach_prompt_path()
    assert not target.exists()
    text, path = cloud_prompt.load_coach_prompt()
    assert path == target
    assert target.exists()
    assert text.strip()  # non-empty seeded content
    # The default instructs the three teaching headings + Anki cards.
    assert "## Your answer, improved" in text
    assert "## What to focus on" in text
    assert "## Anki cards" in text


def test_reads_edited_coach_file_verbatim(_home):
    target = paths.openrouter_coach_prompt_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("MY CUSTOM COACH PROMPT", encoding="utf-8")
    text, _ = cloud_prompt.load_coach_prompt()
    assert text == "MY CUSTOM COACH PROMPT"  # not re-seeded/overwritten


def test_edit_changes_next_coach_load(_home):
    text1, target = cloud_prompt.load_coach_prompt()  # seeds default
    target.write_text("EDITED COACH", encoding="utf-8")
    text2, _ = cloud_prompt.load_coach_prompt()
    assert text2 == "EDITED COACH"
    assert text2 != text1


def test_coach_default_is_its_own_asset_distinct_from_other_prompts(_home):
    # The coach prompt is its OWN packaged asset — distinct from the grammar
    # cloud prompt AND the local _SYSTEM_PROMPT.
    from speakloop.feedback import grammar_analyzer

    text, _ = cloud_prompt.load_coach_prompt()
    asset = (
        Path(cloud_prompt.__file__).parent / "openrouter_coach_prompt_default.txt"
    ).read_text(encoding="utf-8")
    assert text == asset
    assert text != grammar_analyzer._SYSTEM_PROMPT
    grammar_cloud, _ = cloud_prompt.load_cloud_prompt()  # seeds the grammar prompt too
    assert text != grammar_cloud
    # And the loader sources the default from the dedicated coach asset path.
    assert "openrouter_coach_prompt_default.txt" in str(cloud_prompt._DEFAULT_COACH_ASSET)


def test_coach_and_grammar_prompts_use_distinct_files(_home):
    # Seeding the coach prompt does not touch the grammar cloud prompt file.
    cloud_prompt.load_coach_prompt()
    assert paths.openrouter_coach_prompt_path().exists()
    assert not paths.openrouter_prompt_path().exists()
    assert paths.openrouter_coach_prompt_path() != paths.openrouter_prompt_path()
