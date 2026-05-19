"""T095 — `speakloop trends` end-to-end via CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[1] / "fixtures" / "sessions"


def test_trends_renders_three_session_summary():
    runner = CliRunner()
    result = runner.invoke(app, ["trends", "--sessions-dir", str(FIXTURES)])
    assert result.exit_code == 0
    assert "Total sessions:" in result.stdout
    assert "3" in result.stdout


def test_sc_010_14_distinct_dates(tmp_path):
    """SC-010: 14 distinct entries for 14 sessions."""
    base = """---
schema_version: 1
session_id: 2026-{month:02d}-{day:02d}-qx
started_at: 2026-{month:02d}-{day:02d}T19:00:00-07:00
question_id: qx
question: |
  X
attempts:
  - ordinal: 1
    time_budget_seconds: 240
    actual_duration_seconds: 220
    metrics:
      words_total: 100
      speech_rate_wpm: 95.0
      filler_words_count: 5
      filler_density_per_100_words: 5.0
      pauses_count: 12
      mean_pause_ms: 500
      self_corrections_count: 2
  - ordinal: 2
    time_budget_seconds: 180
    actual_duration_seconds: 178
    metrics:
      words_total: 110
      speech_rate_wpm: 100.0
      filler_words_count: 4
      filler_density_per_100_words: 3.6
      pauses_count: 10
      mean_pause_ms: 480
      self_corrections_count: 2
  - ordinal: 3
    time_budget_seconds: 120
    actual_duration_seconds: 120
    metrics:
      words_total: 120
      speech_rate_wpm: 110.0
      filler_words_count: 3
      filler_density_per_100_words: 2.5
      pauses_count: 8
      mean_pause_ms: 400
      self_corrections_count: 1
grammar_patterns: []
generated_by_phase: B
---

# body
"""
    sd = tmp_path / "sessions"
    sd.mkdir()
    for d in range(1, 15):
        (sd / f"2026-05-{d:02d}-qx.md").write_text(base.format(month=5, day=d))

    runner = CliRunner()
    result = runner.invoke(app, ["trends", "--sessions-dir", str(sd)])
    assert result.exit_code == 0
    assert "Total sessions: 14" in result.stdout


def test_empty_state(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    runner = CliRunner()
    result = runner.invoke(app, ["trends", "--sessions-dir", str(empty)])
    assert result.exit_code == 0
    assert "speakloop practice" in result.stdout
