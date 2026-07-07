"""IMP-001 regression — run_session reinstates the prior SIGINT handler on exit.

An inert handler left installed after a completed session swallows every later
Ctrl-C (it only sets abort_event, never raises; PEP 475 then restarts the blocking
read in the debrief menu / question picker). run_session must restore whatever
SIGINT handler was live before it ran, on BOTH the normal-return and abort paths.
"""

from __future__ import annotations

import signal
from pathlib import Path

import pytest

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.sessions import abort as abort_mod
from speakloop.sessions import coordinator
from speakloop.sessions.keyboard import NullKeyReader

pytestmark = pytest.mark.integration


class _Asr:
    def transcribe(self, wav_path, *, context=None):
        return Transcript(text="hello world", audio_duration_seconds=1.0)


def _grammar(transcripts):
    return []


def _record(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 1.0


def _sentinel(signum, frame):  # pragma: no cover - never fires in these tests
    raise KeyboardInterrupt


def test_run_session_restores_prior_sigint_handler(tmp_sessions_dir, tmp_path):
    prior = signal.signal(signal.SIGINT, _sentinel)
    try:
        coordinator.run_session(
            Question(id="x-q", question="q", ideal_answer="a"),
            asr_engine=_Asr(),
            record_fn=_record,
            grammar_analyzer=_grammar,
            sessions_dir=tmp_sessions_dir,
            scratch_dir=tmp_path / "scratch",
            key_reader=NullKeyReader(),
        )
        assert signal.getsignal(signal.SIGINT) is _sentinel
    finally:
        signal.signal(signal.SIGINT, prior)
        abort_mod.reset()


def test_run_session_restores_prior_sigint_handler_on_abort(tmp_sessions_dir, tmp_path):
    def record_then_abort(out_path, time_budget_seconds, early_exit_event):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00")
        if "attempt-2" in str(out_path):
            abort_mod.abort_event.set()
        return 1.0

    prior = signal.signal(signal.SIGINT, _sentinel)
    try:
        with pytest.raises(coordinator.AbortedError):
            coordinator.run_session(
                Question(id="x-q", question="q", ideal_answer="a"),
                asr_engine=_Asr(),
                record_fn=record_then_abort,
                grammar_analyzer=_grammar,
                sessions_dir=tmp_sessions_dir,
                scratch_dir=tmp_path / "scratch",
                key_reader=NullKeyReader(),
            )
        assert signal.getsignal(signal.SIGINT) is _sentinel
    finally:
        signal.signal(signal.SIGINT, prior)
        abort_mod.reset()
