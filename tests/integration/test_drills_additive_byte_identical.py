"""T026 (016) — the pronunciation section is purely additive (SC-003).

A session WITHOUT drills renders a report with NO pronunciation section/key; turning drills
ON inserts exactly that one section and changes nothing else (grammar/coaching/coverage/
transcripts and the whole frontmatter are otherwise byte-identical).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter, report_builder

pytestmark = pytest.mark.integration


def _session(**extra) -> frontmatter.Session:
    return frontmatter.Session(
        session_id="2026-06-12-q07",
        started_at=datetime(2026, 6, 12, 9, 0, 0),
        question_id="q07",
        question_text="Explain coroutines.",
        ideal_answer="A coroutine is a suspendable computation.",
        attempts=[
            frontmatter.Attempt(ordinal=i, time_budget_seconds=b, actual_duration_seconds=b - 1, transcript=f"attempt {i}")
            for i, b in ((1, 240), (2, 180), (3, 120))
        ],
        grammar_patterns=[
            frontmatter.GrammarPattern(
                label="3rd-person singular -s drop",
                occurrence_count=2,
                evidence=[{"attempt_ordinal": 1, "quote": "he run", "corrected": "he runs"}],
                impact_rank=1,
            )
        ],
        generated_by_phase="C",
        **extra,
    )


_DRILLS = {
    "engine_note": "offered because the local feedback model isn't resident",
    "items": [
        {
            "drill_id": "west",
            "text": "west",
            "status": "scored",
            "flags": [
                {
                    "expected": "w",
                    "word": "west",
                    "competitor": "ɹ",
                    "confident_diagnosis": True,
                    "tip": "Round your lips.",
                }
            ],
            "is_follow_on": False,
            "contrast_id": "w_r",
        }
    ],
    "summary": {"drills": 1, "with_flags": 1, "contrasts_practiced": ["w_r"]},
}


def test_no_drills_report_has_no_pronunciation_section_or_key():
    report = report_builder.build(_session())
    assert "## Pronunciation drills" not in report
    assert "pronunciation_drills" not in report  # not in frontmatter either


def test_turning_drills_on_inserts_only_that_section():
    r_none = report_builder.build(_session())
    r_with = report_builder.build(_session(pronunciation_drills=_DRILLS))

    section = report_builder._pronunciation_drills_section(_session(pronunciation_drills=_DRILLS))
    assert section is not None
    assert "## Pronunciation drills" in r_with

    # The body section is inserted immediately before the Transcripts section, and nothing
    # else in the body changes: removing the inserted block recovers the no-drills body.
    body_none = r_none.split("---\n", 2)[2]
    body_with = r_with.split("---\n", 2)[2]
    assert body_with.replace(section + "\n\n", "", 1) == body_none

    # The frontmatter gains exactly the additive `pronunciation_drills:` key and nothing else.
    fm_none = r_none.split("---\n", 2)[1]
    fm_with = r_with.split("---\n", 2)[1]
    assert "pronunciation_drills:" in fm_with
    assert "pronunciation_drills:" not in fm_none
    # schema_version unchanged
    assert "schema_version: 1" in fm_none and "schema_version: 1" in fm_with


def test_frontmatter_round_trips_drills():
    s = _session(pronunciation_drills=_DRILLS)
    text = frontmatter.dump(s)
    back = frontmatter.parse(text)
    assert back.pronunciation_drills == _DRILLS
    # absent ⇒ None (back-compat)
    assert frontmatter.parse(frontmatter.dump(_session())).pronunciation_drills is None
