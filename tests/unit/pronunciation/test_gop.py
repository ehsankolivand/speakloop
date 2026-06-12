"""T007 — CTC forced alignment + GOP on SYNTHETIC posteriors (no model loaded)."""

from __future__ import annotations

import numpy as np
import pytest

from speakloop.pronunciation import gop

pytestmark = pytest.mark.unit


def _logp(rows: list[list[float]]) -> np.ndarray:
    p = np.array(rows, dtype=float)
    p = p / p.sum(axis=1, keepdims=True)
    return np.log(p)


def test_forced_align_is_monotonic_and_covers_blocks():
    # V=4, blank=0; phones 1,2,3 each cleanly dominate a 3-frame block.
    rows = []
    for d in [1, 1, 1, 2, 2, 2, 3, 3, 3]:
        r = [0.04] * 4
        r[d] = 0.88
        rows.append(r)
    logp = _logp(rows)

    spans = gop.forced_align([1, 2, 3], logp, blank_id=0)

    assert len(spans) == 3
    # monotonic, non-overlapping
    assert spans[0][0] <= spans[0][1] < spans[1][0] <= spans[1][1] < spans[2][0] <= spans[2][1]
    # each token lands inside its dominant block
    assert spans[0][1] <= 2
    assert spans[1][0] >= 3 and spans[1][1] <= 5
    assert spans[2][0] >= 6
    # all phones well-pronounced ⇒ GOP near log(0.88)
    scores = gop.gop_scores([1, 2, 3], spans, logp)
    assert all(s > np.log(0.5) for s in scores)


def test_planted_error_lowers_gop_and_names_the_competitor():
    # The middle token (expected phone 2) is read as competitor phone 5.
    V = 6
    rows: list[list[float]] = []
    for d in (1, 1, 1):
        r = [0.02] * V
        r[d] = 0.9
        rows.append(r)
    for _ in range(3):
        r = [0.02] * V
        r[5] = 0.6  # competitor dominates the expected region
        r[2] = 0.3  # expected phone present but weaker
        rows.append(r)
    for d in (3, 3, 3):
        r = [0.02] * V
        r[d] = 0.9
        rows.append(r)
    logp = _logp(rows)

    canonical = [1, 2, 3]
    spans = gop.forced_align(canonical, logp, blank_id=0)
    scores = gop.gop_scores(canonical, spans, logp)

    # the expected phone scored worse than its well-read neighbours (DETECTION)
    assert scores[1] < scores[0]
    assert scores[1] < scores[2]

    # the top competitor over that span is the planted phone 5 (DIAGNOSIS suggestion)
    comp, margin = gop.top_competitor(spans[1], logp, blank_id=0, exclude_id=2)
    assert comp == 5
    assert margin > 0


def test_empty_inputs_return_empty():
    logp = np.log(np.full((0, 4), 0.25)) if False else np.empty((0, 4))
    assert gop.forced_align([], logp, blank_id=0) == []
    assert gop.forced_align([1, 2], np.empty((0, 4)), blank_id=0) == []


def test_more_tokens_than_frames_falls_back_without_crashing():
    # 2 frames, 4 canonical tokens → every token still gets a usable single-frame span.
    rows = [[0.7, 0.1, 0.1, 0.1], [0.1, 0.1, 0.1, 0.7]]
    logp = _logp(rows)
    spans = gop.forced_align([1, 2, 3, 1], logp, blank_id=0)
    assert len(spans) == 4
    assert all(0 <= a <= b < 2 for a, b in spans)
