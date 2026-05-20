"""T062 — SIGINT during attempts leaves no .md and no .tmp."""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.sessions import abort as abort_mod
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration


class _Asr:
    def transcribe(self, wav_path, *, context=None):
        return Transcript(text="x", audio_duration_seconds=1.0)


def test_abort_during_attempt_writes_no_report(tmp_sessions_dir, tmp_path):
    q = Question(id="x-q", question="q", ideal_answer="a")

    def record(out_path, time_budget_seconds, early_exit_event):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00")
        # Simulate the user pressing Ctrl+C during attempt 2.
        if "attempt-2" in str(out_path):
            abort_mod.abort_event.set()
        return 1.0

    with pytest.raises(coordinator.AbortedError):
        coordinator.run_session(
            q,
            asr_engine=_Asr(),
            record_fn=record,
            sessions_dir=tmp_sessions_dir,
            scratch_dir=tmp_path / "scratch",
        )

    abort_mod.reset()
    md = list(tmp_sessions_dir.rglob("*.md"))
    tmp_files = list(tmp_sessions_dir.rglob("*.tmp"))
    assert md == []
    assert tmp_files == []
