"""Full report round-trip with every 010 field populated (T088)."""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, GrammarPattern, Session

pytestmark = pytest.mark.integration


def _full_session() -> Session:
    return Session(
        session_id="2026-06-10-q", started_at=datetime(2026, 6, 10, 9, 0, 0),
        question_id="q", question_text="Q", ideal_answer="A",
        attempts=[Attempt(ordinal=1, time_budget_seconds=240, actual_duration_seconds=200.0,
                          transcript="hi", metrics=AttemptMetrics(words_total=10))],
        grammar_patterns=[GrammarPattern(label="verb tense", occurrence_count=2, impact_rank=1,
                                         evidence=[{"attempt_ordinal": 1, "quote": "hi", "corrected": "hello"}])],
        generated_by_phase="C",
        question_type="hypothetical",
        warmup={"target_pattern": "verb tense", "items": [{"index": 1, "target_sentence": "x", "result": "pass"}]},
        answer_grade="good",
        pattern_trends={"verb tense": "5 → 2"},
        coverage=[{"attempt_ordinal": 1, "key_points_version": 2, "aggregate": 0.5,
                   "per_point": [{"id": 1, "state": "covered"}]}],
        content_errors=[{"attempt_ordinal": 1, "learner_claim": "A11", "ideal_claim": "A12"}],
        key_points={"version": 2, "ideal_answer_hash": "abc", "points": [{"id": 1, "text": "kp"}]},
        pronunciation_flags=[{"attempt_ordinal": 1, "heard": "mouse", "likely_intended": "must"}],
        triage_summary={"real": 3, "mishearing": 1, "hallucination_dropped": 1},
        follow_ups=[{"index": 1, "question_text": "why?", "answered": True, "transcript": "because"}],
        analysis_pending=False,
    )


def test_dump_parse_dump_idempotent_with_all_fields():
    s = _full_session()
    dumped = frontmatter.dump(s)
    assert "schema_version: 1" in dumped
    parsed = frontmatter.parse(dumped)
    # every additive field survives
    assert parsed.question_type == "hypothetical"
    assert parsed.answer_grade == "good"
    assert parsed.pattern_trends == {"verb tense": "5 → 2"}
    assert parsed.coverage[0]["aggregate"] == 0.5
    assert parsed.content_errors[0]["ideal_claim"] == "A12"
    assert parsed.key_points["version"] == 2
    assert parsed.pronunciation_flags[0]["heard"] == "mouse"
    assert parsed.triage_summary["mishearing"] == 1
    assert parsed.follow_ups[0]["question_text"] == "why?"
    assert parsed.warmup["target_pattern"] == "verb tense"
    # idempotent at the serialized level
    assert frontmatter.dump(parsed) == dumped
