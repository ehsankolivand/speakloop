"""T019 (004) — personal-override precedence (US4).

`~/.speakloop/qa.yaml` (when present) is loaded over the in-repo default
content/questions.yaml; when absent, resolution falls back to the in-repo default.
Edge case: when both exist, the override wins.
"""

from __future__ import annotations

import pytest

from speakloop.config import paths

pytestmark = pytest.mark.integration


def test_home_override_wins_when_present(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    monkeypatch.delenv("SPEAKLOOP_QA_FILE", raising=False)
    paths.set_qa_file_path(None)

    override = tmp_path / "qa.yaml"
    override.write_text("schema_version: 1\nquestions: []\n", encoding="utf-8")

    resolved = paths.resolve_qa_file()
    assert resolved == override
    # ...and it wins over the in-repo default, which also exists.
    assert paths.default_qa_file().exists()
    assert resolved != paths.default_qa_file()


def test_falls_back_to_inrepo_default_when_no_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))  # empty → no ~/.speakloop/qa.yaml
    monkeypatch.delenv("SPEAKLOOP_QA_FILE", raising=False)
    paths.set_qa_file_path(None)

    assert not (tmp_path / "qa.yaml").exists()
    resolved = paths.resolve_qa_file()
    assert resolved == paths.default_qa_file()
    assert resolved.exists()


def test_explicit_qa_file_flag_beats_home_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    monkeypatch.delenv("SPEAKLOOP_QA_FILE", raising=False)

    # Both a home override and an explicit --qa-file path exist; the flag wins.
    (tmp_path / "qa.yaml").write_text("schema_version: 1\nquestions: []\n", encoding="utf-8")
    explicit = tmp_path / "my-questions.yaml"
    explicit.write_text("schema_version: 1\nquestions: []\n", encoding="utf-8")
    paths.set_qa_file_path(explicit)
    try:
        assert paths.resolve_qa_file() == explicit
    finally:
        paths.set_qa_file_path(None)
