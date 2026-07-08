"""T012 (018, US1) — rescue-line card derivation + merge from report grammar evidence."""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import Attempt, GrammarPattern, Session
from speakloop.linecards import cards

pytestmark = pytest.mark.unit


def _write_report(tmp, name, patterns, *, qid="activity-x", sid="s1"):
    session = Session(
        session_id=sid,
        started_at=datetime(2026, 7, 1, 10, 0, 0),
        question_id=qid,
        question_text="Some question",
        attempts=[Attempt(ordinal=1, time_budget_seconds=90, actual_duration_seconds=30.0)],
        grammar_patterns=patterns,
    )
    path = tmp / name
    path.write_text(frontmatter.dump(session), encoding="utf-8")
    return path


_ARTICLE = GrammarPattern(
    label="missing article",
    occurrence_count=2,
    explanation="A singular countable noun needs an article.",
    evidence=[
        {"attempt_ordinal": 1, "quote": "new instance of it", "corrected": "a new instance of it"},
        {"attempt_ordinal": 2, "quote": "to user", "corrected": "to the user"},
    ],
)


def test_derive_cards_from_evidence(tmp_path):
    _write_report(tmp_path, "2026-07-01-x.md", [_ARTICLE])
    derived = cards.derive_cards(tmp_path)
    corrected = {c.corrected for c in derived}
    assert corrected == {"a new instance of it", "to the user"}
    one = next(c for c in derived if c.corrected == "a new instance of it")
    assert one.quote == "new instance of it"
    assert one.rule == "A singular countable noun needs an article."
    assert one.question_id == "activity-x"
    assert one.source == "report"


def test_no_op_and_missing_corrections_are_skipped(tmp_path):
    pattern = GrammarPattern(
        label="noise",
        occurrence_count=3,
        evidence=[
            {"attempt_ordinal": 1, "quote": "same words", "corrected": "same words"},  # no-op
            {"attempt_ordinal": 1, "quote": "only a quote"},  # no corrected key
            {"attempt_ordinal": 2, "quote": "system create", "corrected": "system creates"},  # real
        ],
    )
    _write_report(tmp_path, "2026-07-01-x.md", [pattern])
    derived = cards.derive_cards(tmp_path)
    assert [c.corrected for c in derived] == ["system creates"]


def test_identical_correction_across_reports_collapses_to_one_card(tmp_path):
    _write_report(tmp_path, "2026-07-01-a.md", [_ARTICLE], sid="s1")
    _write_report(tmp_path, "2026-07-02-b.md", [_ARTICLE], sid="s2")
    derived = cards.derive_cards(tmp_path)
    assert len(derived) == 2  # deduped by stable card_id, not 4
    ids = {c.card_id for c in derived}
    assert len(ids) == 2


def test_card_id_is_stable_and_field_sensitive():
    a = cards.card_id("q", "you said", "you say")
    assert a == cards.card_id("q", "you said", "you say")  # stable
    assert a != cards.card_id("q2", "you said", "you say")  # question-sensitive
    assert a != cards.card_id("q", "you said", "you said differently")  # correction-sensitive


def test_unreadable_report_is_skipped(tmp_path):
    (tmp_path / "junk.md").write_text("not a speakloop report", encoding="utf-8")
    _write_report(tmp_path, "2026-07-01-x.md", [_ARTICLE])
    assert len(cards.derive_cards(tmp_path)) == 2  # junk skipped, real report folded


def test_merge_keeps_stored_state_and_adds_new_cards():
    c1 = cards.LineCard("id1", "a new instance", "new instance", "rule", "q", "report")
    c2 = cards.LineCard("id2", "system creates", "system create", "rule", "q", "report")
    stored = {"id1": {**cards.content_dict(c1), **cards.new_state(), "total_reviews": 5,
                      "last_grade": "good", "interval_days": 4, "next_due": "2026-07-10"}}
    merged = cards.merge_cards([c1, c2], [], stored)
    assert set(merged) == {"id1", "id2"}
    assert merged["id1"]["total_reviews"] == 5  # existing review history preserved
    assert merged["id1"]["next_due"] == "2026-07-10"
    assert merged["id2"]["total_reviews"] == 0  # brand-new card gets placeholder state
    assert merged["id2"]["next_due"] is None
