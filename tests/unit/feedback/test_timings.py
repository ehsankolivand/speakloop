"""T003 — StageTimer: ordering, overlapped flag, frontmatter shape, fake clock."""

from __future__ import annotations

import pytest

from speakloop.feedback.timings import TIMINGS_SCHEMA, StageTimer

pytestmark = pytest.mark.unit


class _FakeClock:
    """Deterministic, advanceable clock so timings tests never sleep."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_stage_records_in_order_with_durations():
    clk = _FakeClock()
    timer = StageTimer(clock=clk)
    with timer.stage("a"):
        clk.advance(1.5)
    with timer.stage("b"):
        clk.advance(0.5)
    recs = timer.records
    assert [r["name"] for r in recs] == ["a", "b"]
    assert recs[0]["seconds"] == 1.5
    assert recs[1]["seconds"] == 0.5
    assert "overlapped" not in recs[0]


def test_overlapped_flag_emitted_only_when_true():
    clk = _FakeClock()
    timer = StageTimer(clock=clk)
    timer.record("overlap_me", 3.0, overlapped=True)
    timer.record("normal", 2.0)
    assert timer.records[0]["overlapped"] is True
    assert "overlapped" not in timer.records[1]


def test_start_stop_manual_pair():
    clk = _FakeClock()
    timer = StageTimer(clock=clk)
    timer.start("bg")
    clk.advance(4.0)
    timer.stop("bg", overlapped=True)
    assert timer.records == [{"name": "bg", "seconds": 4.0, "overlapped": True}]
    # stop without a matching start is a no-op.
    timer.stop("never_started")
    assert len(timer.records) == 1


def test_zero_duration_cache_hit_case():
    clk = _FakeClock()
    timer = StageTimer(clock=clk)
    with timer.stage("listen_synth_question"):
        pass  # cache hit — no time advanced
    assert timer.records[0]["seconds"] == 0.0


def test_to_frontmatter_shape():
    clk = _FakeClock()
    timer = StageTimer(clock=clk)
    with timer.stage("attempt_1_record"):
        clk.advance(95.0)
    block = timer.to_frontmatter(
        analysis_mode="concurrent", analysis_concurrency=3, analysis_wall_seconds=113.0
    )
    assert block["schema"] == TIMINGS_SCHEMA
    assert block["analysis_mode"] == "concurrent"
    assert block["analysis_concurrency"] == 3
    assert block["analysis_wall_seconds"] == 113.0
    assert block["total_seconds"] == 95.0
    assert block["stages"] == [{"name": "attempt_1_record", "seconds": 95.0}]


def test_to_frontmatter_omits_analysis_fields_when_none():
    block = StageTimer(clock=_FakeClock()).to_frontmatter()
    assert "analysis_mode" not in block
    assert "analysis_concurrency" not in block
    assert "analysis_wall_seconds" not in block
    assert block["stages"] == []
