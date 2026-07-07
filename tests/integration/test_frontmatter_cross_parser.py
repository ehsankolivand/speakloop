"""IMP-043 — both frontmatter readers agree on a `---` inside a block scalar.

Reports written by `feedback.frontmatter.dump` are read back by TWO parsers: the custom
`feedback.frontmatter.parse` (rebuild/resume/debrief) and the third-party `python-frontmatter`
via `trends.reader.read_reports` (the dashboard). The BUG-001 fence-anchoring fix — a standalone
`---` line inside a `question`/`ideal_answer` block scalar must NOT be mistaken for the closing
fence — was regression-tested only on the custom parser. This pins that BOTH readers recover the
same fields and the trends reader does not silently drop the report into `.skipped`.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter, markdown_writer
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, GrammarPattern, Session
from speakloop.trends import reader

pytestmark = pytest.mark.integration


def _session_with_a_rule_in_block_scalars() -> Session:
    return Session(
        session_id="2026-06-12-q1",
        started_at=datetime(2026, 6, 12, 9, 0),
        question_id="q1",
        question_text="Intro line\n---\nAfter the rule",  # standalone `---` mid-block (BUG-001)
        ideal_answer="Reference intro\n---\nReference after the rule",
        attempts=[
            Attempt(ordinal=i, time_budget_seconds=b, actual_duration_seconds=b - 1,
                    transcript=f"attempt {i}", metrics=AttemptMetrics())
            for i, b in ((1, 240), (2, 180), (3, 120))
        ],
        grammar_patterns=[GrammarPattern(label="missing articles", occurrence_count=7, impact_rank=1)],
        generated_by_phase="C",
    )


def test_both_frontmatter_readers_agree_on_a_rule_in_a_block_scalar(tmp_path):
    path = tmp_path / "2026-06-12-q1.md"
    markdown_writer.write_atomic(path, frontmatter.dump(_session_with_a_rule_in_block_scalars()))

    # (1) The custom parser (rebuild/resume/debrief).
    custom = frontmatter.parse(path.read_text(encoding="utf-8"))

    # (2) The third-party python-frontmatter reader (trends dashboard).
    result = reader.read_reports(tmp_path)
    assert result.skipped == [], f"trends reader skipped the report: {result.skipped}"
    assert len(result.reports) == 1
    trend = result.reports[0]

    # Both readers recover the same load-bearing fields (nothing lost after the mid-block `---`).
    assert trend.schema_version == 1
    assert len(custom.attempts) == len(trend.attempts) == 3
    assert custom.generated_by_phase == "C"
    assert (
        [p.label for p in custom.grammar_patterns]
        == [p["label"] for p in trend.grammar_patterns]
        == ["missing articles"]
    )
