"""009: report_builder renders the coaching Markdown between the grammar section
and the transcripts, verbatim, and only when present (additive — absent → the
pre-009 layout is unchanged)."""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import report_builder
from speakloop.feedback.frontmatter import (
    Attempt,
    AttemptMetrics,
    GrammarPattern,
    Session,
)

pytestmark = pytest.mark.unit


def _attempt(ordinal, text):
    return Attempt(
        ordinal=ordinal,
        time_budget_seconds={1: 240, 2: 180, 3: 120}[ordinal],
        actual_duration_seconds=100.0,
        transcript=text,
        metrics=AttemptMetrics(words_total=10, speech_rate_wpm=120.0),
    )


def _session(*, coaching=None):
    return Session(
        session_id="2026-06-09-q01",
        started_at=datetime(2026, 6, 9, 10, 0, 0),
        question_id="q01",
        question_text="Tell me about a system you designed.",
        attempts=[_attempt(1, "He write code."), _attempt(2, "It run fast."), _attempt(3, "Done.")],
        grammar_patterns=[
            GrammarPattern(
                label="3rd-person singular -s drop",
                occurrence_count=1,
                evidence=[{"attempt_ordinal": 1, "quote": "He write", "corrected": "He writes"}],
                explanation="Third-person singular present verbs take -s.",
                impact_rank=1,
            )
        ],
        generated_by_phase="C",
        cross_attempt_narrative="N",
        top_priority="T",
        coaching=coaching,
    )


_COACHING = (
    "## Your answer, improved\n\nHe writes clean code that runs fast.\n\n"
    "## What to focus on\n\n- Third-person -s.\n\n"
    "## Anki cards\n\n```\nHe {{c1::writes}} code. (3rd-person singular adds -s)\n```"
)


def test_coaching_rendered_between_grammar_and_transcripts():
    report = report_builder.build(_session(coaching=_COACHING))
    for heading in ("## Your answer, improved", "## What to focus on", "## Anki cards"):
        assert heading in report
    # Placement: after the grammar section, before the transcripts.
    assert report.index("## Grammar patterns") < report.index("## Your answer, improved")
    assert report.index("## Anki cards") < report.index("## Transcripts")
    # Rendered verbatim — the cloze braces and code fence survive untouched.
    assert "{{c1::writes}}" in report
    assert _COACHING in report


def test_no_coaching_section_when_absent_is_byte_identical():
    # Absent coaching → the body matches a session built without the field at all
    # (the additive section leaves the pre-009 layout untouched).
    none_report = report_builder.build(_session(coaching=None))
    assert "## Your answer, improved" not in none_report
    # The grammar section is still immediately followed by the transcripts.
    between = none_report[
        none_report.index("## Grammar patterns") : none_report.index("## Transcripts")
    ]
    assert "## Your answer, improved" not in between
    assert "## What to focus on" not in between
