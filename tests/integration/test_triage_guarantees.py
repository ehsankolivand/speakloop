"""Trustworthy-pipeline guarantees through the coordinator (010, T073).

SC-003: no ASR-hallucination text reaches grammar evidence.
SC-006: a pronunciation mishearing is surfaced as a pronunciation flag, never as a
grammar error. Stubbed engines — no live models.
"""

from __future__ import annotations

import pytest

from speakloop.asr import SegmentMeta, Transcript
from speakloop.content import Question
from speakloop.sessions import coordinator
from speakloop.triage.hallucination import TriagedSpan

pytestmark = pytest.mark.integration

_HALLUCINATION = "I'll see you later"
_REAL = "the activity is destroyed and recreated on rotation"


class _StubASR:
    """Every attempt: one real segment + one silence-hallucination segment."""

    def transcribe(self, wav_path, *, context=None):
        return Transcript(
            text=f"{_REAL} {_HALLUCINATION}",
            segments=(
                SegmentMeta(0.0, 2.0, _REAL, avg_logprob=-0.2, no_speech_prob=0.02),
                SegmentMeta(2.0, 3.0, _HALLUCINATION, avg_logprob=-1.7, no_speech_prob=0.95),
            ),
            vad_regions=((0.0, 2.0),),
        )


def _record(out_path, time_budget_seconds, early_exit_event):
    from pathlib import Path

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(b"\x00")
    return 3.0


def test_hallucination_never_reaches_grammar_or_report(tmp_sessions_dir, tmp_path):
    from speakloop.feedback.frontmatter import GrammarPattern

    seen_by_grammar: list[str] = []

    def grammar(transcripts):
        seen_by_grammar.extend(t.text for t in transcripts)
        return [GrammarPattern(label="verb tense", occurrence_count=1,
                               evidence=[{"attempt_ordinal": 1, "quote": "the activity"}])]

    runners = coordinator.Runners(
        mishearing=lambda real_text: [
            TriagedSpan(text="mouse", start_seconds=0, end_seconds=0, span_class="mishearing",
                        signal="llm_mishearing", heard="mouse", likely_intended="must")
        ],
    )

    result = coordinator.run_session(
        Question(id="q", question="Q", ideal_answer="A"),
        asr_engine=_StubASR(),
        record_fn=_record,
        grammar_analyzer=grammar,
        runners=runners,
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    )

    # SC-003: the hallucination text was filtered out before grammar saw the transcripts
    joined = " ".join(seen_by_grammar)
    assert _HALLUCINATION not in joined
    assert _REAL in joined

    body = result.report_path.read_text()
    assert _HALLUCINATION not in body                       # not in transcripts/grammar evidence
    assert result.session.triage_summary["hallucination_dropped"] >= 1

    # SC-006: the mishearing is a pronunciation flag, never a grammar pattern
    assert any(f["heard"] == "mouse" for f in result.session.pronunciation_flags)
    assert all("mouse" not in (p.label or "") for p in result.session.grammar_patterns)
    assert "## Pronunciation flags" in body
