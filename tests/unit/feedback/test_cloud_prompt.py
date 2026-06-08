"""008: cloud system-prompt loader — seed-if-missing, read-verbatim, separate
from the local _SYSTEM_PROMPT (FR-012)."""

from __future__ import annotations

import pytest

from speakloop.config import paths
from speakloop.feedback import cloud_prompt

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    return tmp_path


def test_seeds_default_when_missing(_home):
    target = paths.openrouter_prompt_path()
    assert not target.exists()
    text, path = cloud_prompt.load_cloud_prompt()
    assert path == target
    assert target.exists()
    assert text.strip()  # non-empty seeded content
    assert "JSON" in text  # the default instructs the strict JSON schema


def test_reads_edited_file_verbatim(_home):
    target = paths.openrouter_prompt_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("MY CUSTOM CLOUD PROMPT", encoding="utf-8")
    text, _ = cloud_prompt.load_cloud_prompt()
    assert text == "MY CUSTOM CLOUD PROMPT"  # not re-seeded/overwritten


def test_edit_changes_next_load(_home):
    text1, target = cloud_prompt.load_cloud_prompt()  # seeds default
    target.write_text("EDITED", encoding="utf-8")
    text2, _ = cloud_prompt.load_cloud_prompt()
    assert text2 == "EDITED"
    assert text2 != text1


def test_seeded_default_is_separate_asset_not_local_prompt(_home):
    # FR-012: the cloud prompt is its OWN packaged asset, never the local
    # _SYSTEM_PROMPT. The loaded default must equal the dedicated asset file and
    # differ from the local prompt.
    from pathlib import Path

    from speakloop.feedback import grammar_analyzer

    text, _ = cloud_prompt.load_cloud_prompt()
    asset = (
        Path(cloud_prompt.__file__).parent / "openrouter_prompt_default.txt"
    ).read_text(encoding="utf-8")
    assert text == asset
    assert text != grammar_analyzer._SYSTEM_PROMPT
    # And the loader sources the default from the dedicated asset path, not the
    # analyzer's in-memory constant.
    assert "openrouter_prompt_default.txt" in str(cloud_prompt._DEFAULT_ASSET)
