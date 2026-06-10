"""US1 follow-up stage wiring (010-interview-loop) with stubs — no live audio.

Verifies the coordinator: generates follow-ups via the injected runner, "speaks"
them (stub TTS), "records" + transcribes the answer (stubs), and stores them in
``Session.follow_ups`` + renders a Follow-ups report section. The real spoken/
audio/latency behavior is covered by the manual voice smoke test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration


class _StubTTS:
    def __init__(self):
        self.spoken = []

    def synthesize(self, text, voice=None):
        self.spoken.append(text)
        return Path("/dev/null")


class _StubASR:
    """Returns attempt transcripts, then a fixed follow-up answer transcript."""

    def __init__(self, attempts, followup_answer):
        self._queue = list(attempts)
        self._followup_answer = followup_answer

    def transcribe(self, wav_path, *, context=None):
        if self._queue:
            return self._queue.pop(0)
        return self._followup_answer


def _record(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return min(time_budget_seconds, 5.0)


def test_followup_stage_records_and_reports(tmp_sessions_dir, tmp_path):
    q = Question(id="rotation", question="Walk me through rotation.",
                 ideal_answer="The activity is destroyed and recreated.")
    attempts = [Transcript(text="the activity is destroyed and recreated on rotation") for _ in range(3)]
    followup_answer = Transcript(text="the view model is retained through the non configuration instance")

    spoke = _StubTTS()
    runners = coordinator.Runners(
        followups=lambda question_text, transcripts: [
            {"question": "Why is the view model retained?", "probe_ref": "view model",
             "probe_type": "why"}
        ],
    )

    result = coordinator.run_session(
        q,
        tts_engine=spoke,
        play_fn=lambda wav: None,
        asr_engine=_StubASR(attempts, followup_answer),
        record_fn=_record,
        runners=runners,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    )

    session = result.session
    assert len(session.follow_ups) == 1
    fu = session.follow_ups[0]
    assert fu["question_text"] == "Why is the view model retained?"
    assert fu["answered"] is True
    assert "view model is retained" in fu["transcript"]
    # the follow-up was actually spoken (stub TTS captured it)
    assert "Why is the view model retained?" in spoke.spoken

    body = result.report_path.read_text()
    assert "## Follow-ups" in body
    assert "Why is the view model retained?" in body


def test_no_followups_when_runner_absent(tmp_sessions_dir, tmp_path):
    """Without a follow-up runner (e.g. no model), the stage is a no-op."""
    q = Question(id="rotation", question="Q", ideal_answer="A")
    attempts = [Transcript(text="some answer text here") for _ in range(3)]
    result = coordinator.run_session(
        q,
        tts_engine=_StubTTS(),
        play_fn=lambda wav: None,
        asr_engine=_StubASR(attempts, Transcript(text="")),
        record_fn=_record,
        runners=None,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    )
    assert result.session.follow_ups == []
    assert "## Follow-ups" not in result.report_path.read_text()
