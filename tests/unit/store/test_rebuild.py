"""Derived-store rebuild + round-trip tests (010-interview-loop, T027).

Builds a small set of session reports with known grammar patterns, key points, and
grades, then asserts ``store.rebuild`` folds them deterministically and that a JSON
save→load and a second rebuild are idempotent. No byte-exact golden file.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import GrammarPattern, Session
from speakloop.store import io as store_io
from speakloop.store import rebuild as store_rebuild

pytestmark = pytest.mark.unit


def _report(tmp_path, *, date, qid, patterns, grade=None, key_points=None):
    session = Session(
        session_id=f"{date}-{qid}",
        started_at=datetime.fromisoformat(f"{date}T09:00:00"),
        question_id=qid,
        question_text=f"Question {qid}",
        attempts=[],
        grammar_patterns=[
            GrammarPattern(label=label, occurrence_count=count) for label, count in patterns
        ],
        answer_grade=grade,
        key_points=key_points,
    )
    (tmp_path / f"{date}-{qid}.md").write_text(frontmatter.dump(session), encoding="utf-8")


def _sessions(tmp_path):
    _report(tmp_path, date="2026-06-01", qid="q1", patterns=[("verb tense", 10)], grade="poor")
    _report(tmp_path, date="2026-06-05", qid="q1", patterns=[("verb tense", 4)], grade="fair")
    _report(
        tmp_path,
        date="2026-06-10",
        qid="q1",
        patterns=[("verb tense", 1), ("article use", 2)],
        grade="good",
        key_points={"version": 2, "ideal_answer_hash": "abc123",
                    "points": [{"id": 1, "text": "kp one"}]},
    )
    return tmp_path


def test_pattern_series_is_chronological(tmp_path):
    store = store_rebuild.rebuild(_sessions(tmp_path))
    assert store.patterns["verb tense"] == [
        ["2026-06-01", 10], ["2026-06-05", 4], ["2026-06-10", 1]
    ]
    assert store.patterns["article use"] == [["2026-06-10", 2]]


def test_key_points_taken_from_latest(tmp_path):
    store = store_rebuild.rebuild(_sessions(tmp_path))
    assert store.key_points["q1"]["abc123"]["version"] == 2


def test_schedule_records_observed_history(tmp_path):
    store = store_rebuild.rebuild(_sessions(tmp_path))
    entry = store.schedule["q1"]
    assert entry.total_reviews == 3
    assert entry.last_grade == "good"          # latest session's grade
    assert entry.last_practiced == "2026-06-10"


def test_rebuild_is_idempotent(tmp_path):
    s = _sessions(tmp_path)
    assert store_rebuild.rebuild(s).to_dict() == store_rebuild.rebuild(s).to_dict()


def test_json_save_load_round_trip(tmp_path):
    store = store_rebuild.rebuild(_sessions(tmp_path))
    path = tmp_path / "store.json"
    store_io.save_atomic(path, store)
    loaded = store_io.load(path)
    assert loaded.to_dict() == store.to_dict()


def test_rebuild_skips_non_utf8_report_and_folds_valid_siblings(tmp_path):
    """IMP-006: a non-UTF8 `.md` in the sessions dir must not crash the rebuild — the
    read is inside the try, so it is skipped and valid siblings still fold."""
    _sessions(tmp_path)
    # A binary/non-UTF8 file that read_text(encoding="utf-8") cannot decode.
    (tmp_path / "2026-06-06-corrupt.md").write_bytes(b"\xff\xfe\x00\x01 not utf-8 \x80\x81")
    store = store_rebuild.rebuild(tmp_path)
    # The valid siblings folded exactly as before, despite the corrupt file.
    assert store.patterns["verb tense"] == [
        ["2026-06-01", 10], ["2026-06-05", 4], ["2026-06-10", 1]
    ]
    assert store.schedule["q1"].total_reviews == 3


def test_load_missing_returns_empty(tmp_path):
    assert store_io.load(tmp_path / "nope.json").to_dict()["patterns"] == {}


def test_load_corrupt_returns_empty(tmp_path):
    bad = tmp_path / "store.json"
    bad.write_text("{not json", encoding="utf-8")
    assert store_io.load(bad).schedule == {}


@pytest.mark.parametrize(
    "payload",
    [
        '{"schedule": [1, 2, 3]}',  # schedule a list → .items() would AttributeError
        '{"store_version": "abc"}',  # non-numeric version → int() would ValueError
        '{"store_version": null}',  # explicit null version → int() would TypeError
    ],
)
def test_load_valid_json_but_shape_corrupt_returns_empty(tmp_path, payload):
    # A JSON-valid but wrong-shape store must degrade to an empty (rebuildable) Store,
    # not crash the caller — the documented io.load contract.
    bad = tmp_path / "store.json"
    bad.write_text(payload, encoding="utf-8")
    loaded = store_io.load(bad)
    assert loaded.schedule == {}
    assert loaded.to_dict() == store_io.Store().to_dict()
