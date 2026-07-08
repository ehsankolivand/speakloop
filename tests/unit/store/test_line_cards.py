"""T008/T009 (018) — `line_cards` store section round-trip + rebuild fold."""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import Attempt, GrammarPattern, Session
from speakloop.store import rebuild
from speakloop.store.model import Store

pytestmark = pytest.mark.unit


def test_line_cards_round_trip():
    store = Store()
    store.line_cards = {
        "id1": {
            "corrected": "a new instance", "quote": "new instance", "rule": "article",
            "question_id": "q", "source": "report", "cloze": "",
            "last_grade": "good", "interval_days": 4, "next_due": "2026-07-10",
            "consecutive_strong": 0, "mastered": False, "last_practiced": "2026-07-06",
            "total_reviews": 3,
        }
    }
    back = Store.from_dict(store.to_dict())
    assert back.line_cards == store.line_cards


def test_pre_018_store_loads_line_cards_as_empty():
    legacy = {"store_version": 1, "schedule": {}, "key_points": {}, "patterns": {}}
    assert Store.from_dict(legacy).line_cards == {}


def test_rebuild_folds_line_cards_with_placeholder_srs_state(tmp_path):
    session = Session(
        session_id="s1",
        started_at=datetime(2026, 7, 1, 10, 0, 0),
        question_id="q1",
        question_text="Q",
        attempts=[Attempt(ordinal=1, time_budget_seconds=90, actual_duration_seconds=30.0)],
        grammar_patterns=[
            GrammarPattern(
                label="missing article",
                occurrence_count=1,
                explanation="need an article",
                evidence=[{"attempt_ordinal": 1, "quote": "to user", "corrected": "to the user"}],
            )
        ],
    )
    (tmp_path / "2026-07-01-q1.md").write_text(frontmatter.dump(session), encoding="utf-8")

    store = rebuild.rebuild(tmp_path)
    assert len(store.line_cards) == 1
    row = next(iter(store.line_cards.values()))
    assert row["corrected"] == "to the user"
    assert row["rule"] == "need an article"
    assert row["question_id"] == "q1"
    # rebuild restores CONTENT only; scheduling resets to the placeholder (never reviewed)
    assert row["total_reviews"] == 0
    assert row["next_due"] is None
    assert row["last_grade"] is None
