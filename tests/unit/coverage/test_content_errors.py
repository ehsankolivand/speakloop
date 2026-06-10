"""Content-error validation tests (010-interview-loop, T067)."""

from __future__ import annotations

import pytest

from speakloop.coverage.content_errors import validate_content_errors

pytestmark = pytest.mark.unit


def test_keeps_mutually_exclusive_contradiction():
    out = validate_content_errors(
        [{"attempt_ordinal": 3, "learner_claim": "Android 11", "ideal_claim": "Android 12", "key_point_id": 2}]
    )
    assert len(out) == 1
    assert out[0]["learner_claim"] == "Android 11"
    assert out[0]["attempt_ordinal"] == 3
    assert out[0]["key_point_id"] == 2


def test_drops_missing_or_identical_claims():
    out = validate_content_errors([
        {"learner_claim": "", "ideal_claim": "Android 12"},        # missing learner claim
        {"learner_claim": "Android 12", "ideal_claim": ""},        # missing ideal claim
        {"learner_claim": "same", "ideal_claim": "Same"},          # not mutually exclusive
    ])
    assert out == []


def test_handles_none_and_non_dicts():
    assert validate_content_errors(None) == []
    assert validate_content_errors(["nonsense", 5, {"learner_claim": "a", "ideal_claim": "b"}]) == [
        {"learner_claim": "a", "ideal_claim": "b"}
    ]
