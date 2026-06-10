"""T033–T036 — the speed-optimization GATE.

Serial and concurrent analysis MUST produce a byte-identical report given identical
model outputs (FR-027, SC-006); one failed concurrent call degrades only its own
dimension (FR-028); recordings/transcripts survive a mid-analysis failure (FR-029);
timings are recorded. Stubbed engines + fake recorder — no real binary/mic/keyboard.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.coverage.scoring import CoverageResult
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.sessions import coordinator
from speakloop.sessions.coordinator import Runners
from speakloop.sessions.keyboard import NullKeyReader

pytestmark = pytest.mark.integration

_FIXED_NOW = datetime(2026, 6, 10, 9, 0, 0)


def _strip_timings(report: str) -> str:
    """Drop the non-deterministic wall-clock `timings:` frontmatter block before compare.

    Timings are inherently wall-clock (and record the serial/concurrent mode), so they
    are NOT part of analysis-output equivalence; everything else must match exactly."""
    return re.sub(r"(?m)^timings:\n(?: .*\n)*", "", report)


class _StubASR:
    def __init__(self, transcripts):
        self._t = list(transcripts)

    def transcribe(self, wav_path, *, context=None):
        return self._t.pop(0)


def _record_fn(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 3.0


def _span():
    return SimpleNamespace(heard="affect", likely_intended="effect", signal="llm_mishearing")


def _build(*, fail=None, delays=True):
    """Build fixed-output analysis stubs. `fail` names a runner that should raise.

    `delays` adds small, differing sleeps so the concurrent path completes calls OUT of
    insertion order — proving the report assembly is name-keyed, not completion-ordered."""

    def _maybe(name, dt):
        if delays:
            time.sleep(dt)
        if fail == name:
            raise RuntimeError(f"{name} boom")

    def grammar(transcripts):
        _maybe("grammar", 0.05)
        return [
            GrammarPattern(label="article-use", occurrence_count=2, impact_rank=1,
                           evidence=[{"attempt_ordinal": 1, "quote": "a apple"}]),
        ]

    def coach(q, transcripts, patterns):
        _maybe("coaching", 0.02)
        return "CORRECTED ANSWER\n\nFocus on articles."

    def mishearing(real_text):
        _maybe("mishearing", 0.01)
        return [_span()]

    def keypoints(q, ideal, qtype):
        return [{"id": 1, "text": "components"}, {"id": 2, "text": "lifecycle"}]

    def coverage(points, transcripts, ideal, version):
        _maybe("coverage", 0.03)
        return CoverageResult(
            attempt_records=[
                {"attempt_ordinal": 1, "key_points_version": version, "aggregate": 0.5,
                 "per_point": [{"id": 1, "state": "covered"}, {"id": 2, "state": "missed"}]},
                {"attempt_ordinal": 3, "key_points_version": version, "aggregate": 1.0,
                 "per_point": [{"id": 1, "state": "covered"}, {"id": 2, "state": "covered"}]},
            ],
            content_errors=[],
            final_aggregate=1.0,
        )

    def consistency(artifact, ideal):
        return artifact  # unchanged → coaching kept verbatim

    runners = Runners(
        mishearing=mishearing, followups=None, consistency=consistency,
        drill=None, keypoints=keypoints, coverage=coverage,
    )
    return grammar, coach, runners


def _run(*, parallel_safe, tmp_path, fail=None, delays=True, concurrency=3):
    grammar, coach, runners = _build(fail=fail, delays=delays)
    q = Question(id="q01", question="What are the four components?",
                 ideal_answer="Activity, Service, Receiver, Provider.")
    transcripts = [Transcript(text=f"attempt {i} text", audio_duration_seconds=3.0) for i in (1, 2, 3)]
    result = coordinator.run_session(
        q,
        asr_engine=_StubASR(transcripts),
        record_fn=_record_fn,
        grammar_analyzer=grammar,
        coach=coach,
        runners=runners,
        sessions_dir=tmp_path,
        scratch_dir=tmp_path / "scratch",
        now=lambda: _FIXED_NOW,
        analysis_parallel_safe=parallel_safe,
        analysis_concurrency=concurrency,
        key_reader=NullKeyReader(),
    )
    return result


def test_serial_and_concurrent_reports_are_byte_identical(tmp_path):
    serial = _run(parallel_safe=False, tmp_path=tmp_path / "serial").report_path.read_text()
    concurrent = _run(parallel_safe=True, tmp_path=tmp_path / "concurrent").report_path.read_text()
    assert _strip_timings(serial) == _strip_timings(concurrent)
    # And they really did run in different modes.
    assert "analysis_mode: serial" in serial
    assert "analysis_mode: concurrent" in concurrent


def test_concurrent_path_records_concurrent_mode_and_timings(tmp_path):
    res = _run(parallel_safe=True, tmp_path=tmp_path, concurrency=3)
    timings = res.session.timings
    assert timings is not None
    assert timings["analysis_mode"] == "concurrent"
    assert timings["analysis_concurrency"] == 3
    names = {s["name"] for s in timings["stages"]}
    assert {"analysis_grammar", "analysis_mishearing", "analysis_coverage", "analysis_coaching"} <= names
    assert any(n.startswith("attempt_") for n in names)


def test_one_failed_concurrent_call_degrades_only_itself(tmp_path):
    """FR-028: coverage fails; grammar + coaching still land; only coverage is pending."""
    res = _run(parallel_safe=True, tmp_path=tmp_path, fail="coverage")
    s = res.session
    assert s.grammar_patterns  # grammar succeeded
    assert s.coaching  # coaching succeeded
    assert s.coverage == []  # coverage degraded
    assert s.analysis_pending is True  # only because coverage failed
    assert s.generated_by_phase == "C"  # grammar still made phase C
    assert res.report_path.exists()  # report still written


def test_grammar_failure_keeps_recordings_and_writes_pending_report(tmp_path):
    """FR-029: a mid-analysis failure never costs the recordings/transcripts."""
    res = _run(parallel_safe=True, tmp_path=tmp_path, fail="grammar")
    s = res.session
    assert s.generated_by_phase == "B"
    assert s.phase_c_error and "RuntimeError" in s.phase_c_error
    assert s.analysis_pending is True
    # The attempt recordings survive on disk (resumable), exactly as today.
    scratch = tmp_path / "scratch"
    assert sorted(p.name for p in scratch.glob("attempt-*.wav")) == [
        "attempt-1.wav", "attempt-2.wav", "attempt-3.wav"
    ]


def test_serial_equals_concurrent_even_with_a_failing_call(tmp_path):
    """The byte-identical guarantee holds when a call fails, too."""
    serial = _run(parallel_safe=False, tmp_path=tmp_path / "s", fail="coaching").report_path.read_text()
    concurrent = _run(parallel_safe=True, tmp_path=tmp_path / "c", fail="coaching").report_path.read_text()
    assert _strip_timings(serial) == _strip_timings(concurrent)
