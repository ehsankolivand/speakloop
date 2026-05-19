"""T092 — trends.reader."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from speakloop.trends import reader

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parents[2] / "fixtures" / "sessions"


def test_reads_three_speakloop_reports():
    result = reader.read_reports(FIXTURES)
    assert len(result.reports) == 3
    ids = sorted(r.session_id for r in result.reports)
    assert ids == ["2026-05-15-q1", "2026-05-17-q1", "2026-05-18-q2"]


def test_skips_non_speakloop_silently():
    result = reader.read_reports(FIXTURES)
    # non-speakloop.md is silently skipped (no entry in skipped list).
    skipped_paths = {p.name for p, _ in result.skipped}
    assert "non-speakloop.md" not in skipped_paths


def test_malformed_frontmatter_is_skipped_with_warning():
    result = reader.read_reports(FIXTURES)
    skipped_names = {p.name for p, _ in result.skipped}
    assert "malformed.md" in skipped_names


def test_since_filter_honored():
    result = reader.read_reports(FIXTURES, since=date(2026, 5, 17))
    ids = sorted(r.session_id for r in result.reports)
    assert ids == ["2026-05-17-q1", "2026-05-18-q2"]
