"""T027 (017) — the cross-session pronunciation weak-sound tally in the derived store.

Asserts the additive `pronunciation_contrasts` section round-trips, an old store loads it as
empty, `weak_contrasts()` orders most-weak-first (and is empty with no history), and `rebuild`
folds the tally from each report's `pronunciation_drills` data (so it stays rebuildable).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import Session
from speakloop.store import rebuild as store_rebuild
from speakloop.store.model import Store

pytestmark = pytest.mark.unit


def test_round_trip_and_old_store_defaults_empty():
    s = Store()
    s.record_contrasts({"v_w": 2, "l_r": 1}, date_iso="2026-06-12")
    again = Store.from_dict(s.to_dict())
    assert again.pronunciation_contrasts == {"v_w": [["2026-06-12", 2]], "l_r": [["2026-06-12", 1]]}
    # an old store JSON with no key loads to an empty tally (back-compatible).
    assert Store.from_dict({"store_version": 1}).pronunciation_contrasts == {}


def test_weak_contrasts_orders_most_weak_first_else_empty():
    assert Store().weak_contrasts() == []  # no history → empty → curated fallback
    s = Store()
    s.record_contrasts({"v_w": 1}, date_iso="2026-06-10")
    s.record_contrasts({"v_w": 2, "th_s": 3}, date_iso="2026-06-12")
    # totals: v_w=3, th_s=3 → tie broken by id; both ahead of nothing else.
    assert s.weak_contrasts() == ["th_s", "v_w"]


def test_record_contrasts_ignores_zero_and_empty():
    s = Store()
    s.record_contrasts({"v_w": 0, "": 5}, date_iso="2026-06-12")
    assert s.pronunciation_contrasts == {}


def _report_with_drills(tmp_path, *, date, qid, items):
    session = Session(
        session_id=f"{date}-{qid}",
        started_at=datetime.fromisoformat(f"{date}T09:00:00"),
        question_id=qid,
        question_text=f"Q {qid}",
        attempts=[],
        pronunciation_drills={"items": items, "summary": {"drills": len(items)}},
    )
    (tmp_path / f"{date}-{qid}.md").write_text(frontmatter.dump(session), encoding="utf-8")


def test_rebuild_folds_flagged_contrasts_from_reports(tmp_path):
    _report_with_drills(
        tmp_path, date="2026-06-10", qid="q1",
        items=[
            {"contrast_id": "v_w", "flags": [{"expected": "v"}]},
            {"contrast_id": "l_r", "flags": []},  # clean → not counted
            {"contrast_id": "v_w", "flags": [{"expected": "v"}]},
        ],
    )
    store = store_rebuild.rebuild(tmp_path)
    # v_w flagged twice in one session → one [date, 2] point; l_r clean → absent.
    assert store.pronunciation_contrasts == {"v_w": [["2026-06-10", 2]]}
    assert store.weak_contrasts() == ["v_w"]
