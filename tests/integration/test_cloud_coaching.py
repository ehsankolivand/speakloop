"""009: cloud coaching — coordinator wiring + graceful degradation.

A `coach` callable is run ONLY after a SUCCESSFUL grammar analysis; its free-form
Markdown is appended to the report between the grammar section and the
transcripts. The coach receives the question text + transcripts + verified
patterns (never the ideal answer). Any coach failure degrades gracefully: no
coaching section, a non-fatal `coach_error` note in frontmatter, the grammar
report intact. A degraded grammar step skips coaching entirely.

Mirrors tests/integration/test_phase_c_report.py and test_phase_c_error_persisted.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from speakloop.asr import Transcript
from speakloop.content import Question
from speakloop.feedback import frontmatter
from speakloop.feedback.frontmatter import GrammarPattern
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


_TRANSCRIPTS = [
    Transcript(text="He write a function.", audio_duration_seconds=2.0),
    Transcript(text="The system handle users.", audio_duration_seconds=2.0),
    Transcript(text="A coroutine run on dispatcher.", audio_duration_seconds=2.0),
]

_COACH_MD = (
    "## Your answer, improved\n\nHe writes a function that runs on the dispatcher.\n\n"
    "## What to focus on\n\n- Third-person -s: say \"he writes\".\n\n"
    "## Anki cards\n\n```\nHe {{c1::writes}} a function. (3rd-person singular adds -s)\n```"
)


def _patterns():
    return [
        GrammarPattern(
            label="3rd-person singular -s drop",
            occurrence_count=1,
            evidence=[{"attempt_ordinal": 1, "quote": "He write", "corrected": "He writes"}],
            explanation="Third-person singular present verbs take -s.",
            impact_rank=1,
        )
    ]


def _grammar_ok(_ts):
    return _patterns()


def _run(tmp_sessions_dir, tmp_path, *, grammar, coach):
    q = Question(
        id="q01",
        question="Tell me about coroutines.",
        ideal_answer="An ideal reference answer that must never reach the coach.",
    )
    return coordinator.run_session(
        q,
        asr_engine=_StubASR(_TRANSCRIPTS),
        record_fn=_stub_record,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
        grammar_analyzer=grammar,
        coach=coach,
    ).report_path


def test_coach_success_appends_sections_between_grammar_and_transcripts(
    tmp_sessions_dir, tmp_path
):
    seen: dict = {}

    def coach_runner(question_text, transcripts, patterns):
        seen["question_text"] = question_text
        seen["transcripts"] = transcripts
        seen["patterns"] = patterns
        return _COACH_MD

    path = _run(tmp_sessions_dir, tmp_path, grammar=_grammar_ok, coach=coach_runner)
    text = path.read_text()

    # The three coaching headings are present…
    for heading in ("## Your answer, improved", "## What to focus on", "## Anki cards"):
        assert heading in text
    # …placed AFTER the grammar section and BEFORE the transcripts.
    assert text.index("## Grammar patterns") < text.index("## Your answer, improved")
    assert text.index("## Anki cards") < text.index("## Transcripts")
    # Rendered verbatim (cloze braces survive).
    assert "{{c1::writes}}" in text

    # The coach received the QUESTION text + transcripts + patterns — never the
    # ideal/reference answer.
    assert seen["question_text"] == "Tell me about coroutines."
    assert "reference answer" not in seen["question_text"].lower()
    assert len(seen["transcripts"]) == 3
    assert seen["patterns"][0].label == "3rd-person singular -s drop"

    fm = yaml.safe_load(text.split("---\n", 2)[1])
    assert fm["generated_by_phase"] == "C"
    # Success → no error note; coaching text is body-only, not in frontmatter.
    assert "coach_error" not in fm
    assert "coaching" not in fm


def test_coach_failure_degrades_gracefully(tmp_sessions_dir, tmp_path):
    def coach_runner(question_text, transcripts, patterns):
        raise LLMEngineError("OpenRouter request errored: timed out.")

    path = _run(tmp_sessions_dir, tmp_path, grammar=_grammar_ok, coach=coach_runner)
    text = path.read_text()
    fm = yaml.safe_load(text.split("---\n", 2)[1])

    # Grammar report intact (Phase C, the pattern still present)…
    assert fm["generated_by_phase"] == "C"
    assert len(fm["grammar_patterns"]) == 1
    # …no coaching sections leaked into the body…
    assert "## Your answer, improved" not in text
    assert "## Anki cards" not in text
    # …but a non-fatal coach_error note is persisted and round-trips.
    assert "coach_error" in fm
    assert "timed out" in fm["coach_error"]
    assert "LLMEngineError" in fm["coach_error"]
    parsed = frontmatter.parse(text)
    assert parsed.coach_error is not None and "timed out" in parsed.coach_error
    # The grammar failure note must NOT appear (grammar succeeded).
    assert "phase_c_error" not in fm


def test_coach_skipped_when_grammar_degraded(tmp_sessions_dir, tmp_path):
    called = {"coach": False}

    def failing_grammar(_ts):
        raise LLMEngineError("could not parse grammar response")

    def coach_runner(*_a, **_k):
        called["coach"] = True
        return "## Your answer, improved\n\nshould never appear"

    path = _run(tmp_sessions_dir, tmp_path, grammar=failing_grammar, coach=coach_runner)
    text = path.read_text()
    fm = yaml.safe_load(text.split("---\n", 2)[1])

    # Grammar degraded → coach never ran; no coaching, no coach_error.
    assert called["coach"] is False
    assert fm["generated_by_phase"] == "B"
    assert "phase_c_error" in fm
    assert "coach_error" not in fm
    assert "## Your answer, improved" not in text


def test_no_coach_callable_is_a_clean_phase_c_report(tmp_sessions_dir, tmp_path):
    # Local mode passes coach=None: a normal Phase-C report, no coaching, no error.
    path = _run(tmp_sessions_dir, tmp_path, grammar=_grammar_ok, coach=None)
    text = path.read_text()
    fm = yaml.safe_load(text.split("---\n", 2)[1])
    assert fm["generated_by_phase"] == "C"
    assert "## Your answer, improved" not in text
    assert "coach_error" not in fm
