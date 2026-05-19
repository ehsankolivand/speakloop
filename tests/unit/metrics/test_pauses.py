"""T054 — pauses metric. 250 ms threshold (FR-012b)."""

from __future__ import annotations

import pytest

from speakloop.asr import WordTiming
from speakloop.metrics import pauses

pytestmark = pytest.mark.unit


def _wt(seq):
    """Build a list of WordTiming from (start, end) tuples."""
    return [WordTiming(f"w{i}", s, e) for i, (s, e) in enumerate(seq)]


def test_threshold_excludes_short_gaps():
    # gaps: 0.1, 0.1, 0.1 — all below 250 ms.
    words = _wt([(0, 0.5), (0.6, 1.0), (1.1, 1.5), (1.6, 2.0)])
    r = pauses.compute(words)
    assert r["pauses_count"] == 0


def test_threshold_includes_long_gaps():
    # gaps: 0.3, 0.5 → both ≥ 250 ms.
    words = _wt([(0, 0.5), (0.8, 1.2), (1.7, 2.0)])
    r = pauses.compute(words)
    assert r["pauses_count"] == 2
    assert r["mean_pause_ms"] == pytest.approx(400.0, rel=0.01)


def test_threshold_is_only_knob():
    words = _wt([(0, 0.5), (1.0, 1.5)])  # gap 500ms
    assert pauses.compute(words, threshold_ms=100)["pauses_count"] == 1
    assert pauses.compute(words, threshold_ms=1000)["pauses_count"] == 0


def test_empty_or_single_word_returns_zero():
    assert pauses.compute([])["pauses_count"] == 0
    assert pauses.compute(_wt([(0, 1)]))["pauses_count"] == 0
