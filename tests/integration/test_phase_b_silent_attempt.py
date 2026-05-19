"""T064 — silent attempt does not crash; metrics record zeros; report still produced."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration


class _Asr:
    def __init__(self, transcripts):
        self._iter = iter(transcripts)

    def transcribe(self, wav_path):
        return next(self._iter)


def _stub_record(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 1.0


def test_silent_attempt_2_yields_zero_metrics(tmp_sessions_dir, tmp_path):
    q = Question(id="silent-q", question="Q", ideal_answer="A")
    transcripts = [
        Transcript(text="hello world", audio_duration_seconds=1.0),
        Transcript(text="", audio_duration_seconds=1.0),  # silent
        Transcript(text="hello again", audio_duration_seconds=1.0),
    ]
    path = coordinator.run_session(
        q,
        asr_engine=_Asr(transcripts),
        record_fn=_stub_record,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    )
    fm = yaml.safe_load(path.read_text().split("---\n", 2)[1])
    silent = fm["attempts"][1]
    assert silent["metrics"]["words_total"] == 0
    assert silent["metrics"]["speech_rate_wpm"] == 0.0
