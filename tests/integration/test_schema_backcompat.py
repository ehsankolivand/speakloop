"""Schema back-compat + round-trip for the 010 frontmatter additions (T028).

Backs SC-012: pre-feature reports still parse unchanged, and the new additive keys
round-trip (`dump → parse → dump` idempotent) without bumping `schema_version`.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from speakloop.feedback import frontmatter

pytestmark = pytest.mark.integration

_SESSIONS_DIR = Path(__file__).parents[1] / "fixtures" / "sessions"
# Real report fixtures follow the YYYY-MM-DD-<qid>.md convention; the `malformed`
# and `non-speakloop` fixtures are intentionally bad and excluded here.
_REPORT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _speakloop_reports() -> list[Path]:
    return [p for p in sorted(_SESSIONS_DIR.glob("*.md")) if _REPORT_NAME.match(p.name)]


def test_existing_reports_still_parse():
    """Every pre-feature session fixture parses with schema_version still 1."""
    reports = _speakloop_reports()
    assert reports, "expected committed session fixtures"
    for path in reports:
        session = frontmatter.parse(path.read_text(encoding="utf-8"))
        assert session.session_id != ""
        # new additive fields default cleanly on a pre-feature report
        assert session.question_type == "definition"
        assert session.follow_ups == []
        assert session.coverage == []
        assert session.answer_grade is None
        assert session.analysis_pending is False


def test_new_fields_round_trip_idempotent():
    """A session carrying every new field round-trips dump→parse→dump."""
    session = frontmatter.Session(
        session_id="2026-06-10-anr",
        started_at=datetime(2026, 6, 10, 9, 0, 0),
        question_id="anr-on-startup",
        question_text="If your app ANRs on startup, how would you debug it?",
        attempts=[],
        question_type="hypothetical",
        warmup={"target_pattern": "modal + base verb", "items": [
            {"index": 1, "target_sentence": "You must restart the service.", "result": "pass"},
        ]},
        follow_ups=[
            {"index": 1, "question_text": "Why does blocking the main thread cause an ANR?",
             "probe_ref": "main thread", "answered": True,
             "metrics": {"words_total": 30, "speech_rate_wpm": 90.0}},
        ],
        coverage=[
            {"attempt_ordinal": 1, "aggregate": 0.4,
             "per_point": [{"id": 1, "state": "covered"}, {"id": 2, "state": "missed"}]},
        ],
        content_errors=[
            {"attempt_ordinal": 3, "learner_claim": "Android 11",
             "ideal_claim": "Android 12", "key_point_id": 2},
        ],
        pronunciation_flags=[
            {"attempt_ordinal": 2, "heard": "mouse", "likely_intended": "must",
             "signal": "llm_mishearing"},
        ],
        key_points={"version": 2, "ideal_answer_hash": "9f2c",
                    "points": [{"id": 1, "text": "ANR fires when the main thread is blocked > 5s"}]},
        answer_grade="good",
        analysis_pending=False,
        triage_summary={"real": 41, "mishearing": 1, "hallucination_dropped": 2},
    )

    dumped = frontmatter.dump(session)
    assert "schema_version: 1" in dumped
    parsed = frontmatter.parse(dumped)

    assert parsed.question_type == "hypothetical"
    assert parsed.warmup["target_pattern"] == "modal + base verb"
    assert parsed.follow_ups[0]["question_text"].startswith("Why does")
    assert parsed.coverage[0]["per_point"][1]["state"] == "missed"
    assert parsed.content_errors[0]["learner_claim"] == "Android 11"
    assert parsed.pronunciation_flags[0]["heard"] == "mouse"
    assert parsed.key_points["version"] == 2
    assert parsed.answer_grade == "good"
    assert parsed.triage_summary["hallucination_dropped"] == 2

    # dump → parse → dump is idempotent at the serialized level
    assert frontmatter.dump(parsed) == dumped


def test_analysis_pending_emitted_only_when_true():
    base = frontmatter.Session(
        session_id="s", started_at=datetime(2026, 6, 10), question_id="q",
        question_text="q", attempts=[],
    )
    assert "analysis_pending" not in frontmatter.dump(base)
    base.analysis_pending = True
    assert "analysis_pending: true" in frontmatter.dump(base)
