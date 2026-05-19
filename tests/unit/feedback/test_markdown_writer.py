"""T058 — atomic write contract."""

from __future__ import annotations

import os

import pytest

from speakloop.feedback import markdown_writer

pytestmark = pytest.mark.unit


def test_atomic_write_replaces_target(tmp_path):
    target = tmp_path / "report.md"
    markdown_writer.write_atomic(target, "hello world\n")
    assert target.read_text() == "hello world\n"
    # No .tmp left behind on success.
    assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


def test_crash_before_replace_leaves_no_target(tmp_path, monkeypatch):
    target = tmp_path / "report.md"

    def fake_replace(src, dst):
        raise RuntimeError("simulated crash between flush and rename")

    monkeypatch.setattr(os, "replace", fake_replace)

    with pytest.raises(RuntimeError):
        markdown_writer.write_atomic(target, "content that must not reach disk\n")

    assert not target.exists()
    # The tmp file is left behind — abort handler is responsible for cleanup.
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 1


def test_next_available_path_appends_suffix(tmp_path):
    p1 = markdown_writer.next_available_path(tmp_path, "2026-05-18", "kotlin")
    assert p1.name == "2026-05-18-kotlin.md"
    p1.write_text("first")

    p2 = markdown_writer.next_available_path(tmp_path, "2026-05-18", "kotlin")
    assert p2.name == "2026-05-18-kotlin-2.md"
    p2.write_text("second")

    p3 = markdown_writer.next_available_path(tmp_path, "2026-05-18", "kotlin")
    assert p3.name == "2026-05-18-kotlin-3.md"
