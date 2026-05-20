"""When the Phase-C analyzer raises, the failure is persisted in the report.

Guards the diagnosability fix: a swallowed analyzer exception must surface in the
saved file (frontmatter `phase_c_error` + a Markdown note) so it no longer
requires terminal scrollback. The session still completes as Phase B.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.feedback import frontmatter
from speakloop.llm.interface import LLMEngineError
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration


class _StubASR:
    def __init__(self, transcripts):
        self._iter = iter(transcripts)

    def transcribe(self, wav_path, *, context=None):
        return next(self._iter)


def _stub_record(out_path, time_budget_seconds, early_exit_event):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 1.0


def test_analyzer_exception_is_persisted_as_phase_c_error(tmp_sessions_dir, tmp_path):
    transcripts = [
        Transcript(text="He write a function.", audio_duration_seconds=2.0),
        Transcript(text="The system handle users.", audio_duration_seconds=2.0),
        Transcript(text="A coroutine run on dispatcher.", audio_duration_seconds=2.0),
    ]

    def failing_analyzer(_ts):
        raise LLMEngineError("LLM response contains <think> leakage; engine misconfigured.")

    q = Question(id="kotlin-coroutines-basics", question="Q", ideal_answer="A")
    path = coordinator.run_session(
        q,
        asr_engine=_StubASR(transcripts),
        record_fn=_stub_record,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
        grammar_analyzer=failing_analyzer,
    ).report_path

    text = path.read_text()
    fm = yaml.safe_load(text.split("---\n", 2)[1])

    # Fell back to Phase B with no patterns…
    assert fm["generated_by_phase"] == "B"
    assert fm.get("grammar_patterns", []) == []
    # …but the failure is now persisted in the report (frontmatter + body).
    assert "phase_c_error" in fm
    assert "<think> leakage" in fm["phase_c_error"]
    assert "LLMEngineError" in fm["phase_c_error"]
    assert "Phase C analysis failed" in text  # the Markdown diagnostic note

    # And it round-trips through the parser.
    parsed = frontmatter.parse(text)
    assert parsed.phase_c_error is not None
    assert "<think> leakage" in parsed.phase_c_error


def test_no_phase_c_error_key_when_analysis_succeeds(tmp_sessions_dir, tmp_path):
    transcripts = [Transcript(text="ok", audio_duration_seconds=1.0)] * 3
    q = Question(id="kotlin-coroutines-basics", question="Q", ideal_answer="A")
    # No grammar_analyzer → clean Phase B, no error key emitted.
    path = coordinator.run_session(
        q,
        asr_engine=_StubASR(transcripts),
        record_fn=_stub_record,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    ).report_path
    assert "phase_c_error" not in path.read_text()
