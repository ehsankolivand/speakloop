"""009: the cloud coaching call (feedback/coach.py).

Pure-logic tests with a fake LLM engine — no live network. Verify that the coach
USER prompt carries the question + attempts + detected patterns but NOT the
reference/ideal answer (so the model fixes the speaker's own words), that a
successful call returns the model's Markdown verbatim with a generous token
budget, and that an empty response raises LLMEngineError (the graceful-degradation
seam the coordinator relies on)."""

from __future__ import annotations

import pytest

from speakloop.asr import Transcript
from speakloop.feedback import coach
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.llm import LLMEngineError

pytestmark = pytest.mark.unit


_TS = [
    Transcript(text="I have eight year experience.", audio_duration_seconds=10.0),
    Transcript(text="I work on payment system.", audio_duration_seconds=10.0),
    Transcript(text="I enjoy building reliable services.", audio_duration_seconds=10.0),
]
_PATTERNS = [
    GrammarPattern(
        label="missing plural -s",
        occurrence_count=1,
        evidence=[{"attempt_ordinal": 1, "quote": "eight year", "corrected": "eight years"}],
        explanation="Use the plural after a number greater than one.",
        impact_rank=1,
    )
]


class _FakeLLM:
    """Records the generate(...) call so tests can assert what the coach sent."""

    def __init__(self, content="## Your answer, improved\n\nGood answer."):
        self.content = content
        self.calls: list[dict] = []

    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        self.calls.append(
            {
                "system": system_prompt,
                "user": user_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "retry": retry,
            }
        )
        return self.content


def test_user_prompt_carries_question_attempts_and_patterns():
    prompt = coach.build_user_prompt("Tell me about a system you built.", _TS, _PATTERNS)
    assert "Tell me about a system you built." in prompt
    assert "Attempt 1:" in prompt and "Attempt 2:" in prompt and "Attempt 3:" in prompt
    assert "eight year experience" in prompt
    # The detected grammar pattern (label + quote -> corrected) is included.
    assert "missing plural -s" in prompt
    assert "eight years" in prompt


def test_user_prompt_excludes_the_reference_answer():
    # The coach must fix the speaker's OWN words, not parrot a model answer, so
    # the ideal/reference answer is never assembled into its prompt.
    prompt = coach.build_user_prompt("Q", _TS, _PATTERNS).lower()
    assert "reference answer" not in prompt
    assert "ideal answer" not in prompt


def test_build_user_prompt_handles_no_patterns():
    prompt = coach.build_user_prompt("Q", _TS, [])
    assert "Attempt 1:" in prompt
    # A clear, non-crashing signal when nothing was detected.
    assert "No grammar issues" in prompt


def test_coach_returns_markdown_and_sends_coach_prompt_verbatim():
    llm = _FakeLLM(
        content="## Your answer, improved\n\nClean.\n\n## What to focus on\n\nx\n\n"
        "## Anki cards\n\n```\ncard\n```"
    )
    out = coach.coach("Q", _TS, _PATTERNS, llm, system_prompt="COACH SYSTEM PROMPT")
    assert out.startswith("## Your answer, improved")
    assert "## Anki cards" in out
    # The coach system prompt is sent verbatim as the system message.
    assert llm.calls[0]["system"] == "COACH SYSTEM PROMPT"
    # Generous budget for the long-form teaching section.
    assert llm.calls[0]["max_tokens"] == 2048
    # The intentional, documented coaching temperature (grounded prose, no drift
    # into invented facts) is sent — locking the value so a stray change is caught.
    assert llm.calls[0]["temperature"] == 0.4 == coach._COACH_TEMPERATURE
    # retry stays False — the JSON nudge it injects has no place in free-form prose.
    assert llm.calls[0]["retry"] is False


def test_coach_strips_surrounding_whitespace():
    llm = _FakeLLM(content="\n\n## Your answer, improved\n\nHi.\n\n")
    out = coach.coach("Q", _TS, _PATTERNS, llm, system_prompt="P")
    assert out == "## Your answer, improved\n\nHi."


@pytest.mark.parametrize("empty", ["", "   ", "\n\t  \n"])
def test_coach_raises_on_empty_response(empty):
    llm = _FakeLLM(content=empty)
    with pytest.raises(LLMEngineError):
        coach.coach("Q", _TS, _PATTERNS, llm, system_prompt="P")
