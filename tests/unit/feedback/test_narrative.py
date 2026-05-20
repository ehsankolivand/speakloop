"""T015 — deterministic cross-attempt narrative + Top priority (FR-008, research.md §g).

Most-impactful-wins: a severe grammar pattern wins; a severe fluency issue wins
even when mild grammar patterns exist; silent attempts degrade to the documented
default; output is deterministic across runs.
"""

from __future__ import annotations

import pytest

from speakloop.feedback import narrative
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, GrammarPattern

pytestmark = pytest.mark.unit


def _attempt(ordinal: int, *, wpm: float, filler: float, words: int = 120) -> Attempt:
    return Attempt(
        ordinal=ordinal,
        time_budget_seconds={1: 240, 2: 180, 3: 120}[ordinal],
        actual_duration_seconds=100.0,
        transcript="some speech",
        metrics=AttemptMetrics(
            words_total=words,
            speech_rate_wpm=wpm,
            filler_words_count=int(filler),
            filler_density_per_100_words=filler,
            pauses_count=3,
            mean_pause_ms=500.0,
            self_corrections_count=0,
        ),
    )


def _gerund_pattern() -> GrammarPattern:
    return GrammarPattern(
        label="gerund/infinitive confusion",
        occurrence_count=3,
        evidence=[{"attempt_ordinal": 1, "quote": "I like to programming", "corrected": "I like programming"}],
        explanation="Persian does not split verbs into -ing vs to complements.",
        impact_rank=2,
        catalog_id="gerund-infinitive-confusion",
    )


def _mild_article_pattern() -> GrammarPattern:
    return GrammarPattern(
        label="definite/indefinite article omission (common nouns)",
        occurrence_count=2,
        evidence=[{"attempt_ordinal": 1, "quote": "runs on dispatcher", "corrected": "runs on a dispatcher"}],
        explanation="Persian has no article.",
        impact_rank=4,
    )


# Good fluency: no fluency candidate fires.
GOOD_FLUENCY = [
    _attempt(1, wpm=116, filler=2.5),
    _attempt(2, wpm=128, filler=2.0),
    _attempt(3, wpm=138, filler=1.5),
]


def test_severe_grammar_pattern_wins():
    top = narrative.select_top_priority([_gerund_pattern()], GOOD_FLUENCY)
    assert "gerund/infinitive confusion" in top
    assert "I like programming" in top  # the corrected version
    assert "I like to programming" in top  # the original


def test_severe_fluency_wins_over_mild_grammar():
    # High filler density (rank 1) must beat a mild article omission (rank 4).
    high_filler = [
        _attempt(1, wpm=120, filler=9.0),
        _attempt(2, wpm=122, filler=8.5),
        _attempt(3, wpm=125, filler=8.2),
    ]
    top = narrative.select_top_priority([_mild_article_pattern()], high_filler)
    assert "filler" in top.lower()
    assert "article" not in top.lower()


def test_low_speech_rate_can_be_top_priority():
    slow = [
        _attempt(1, wpm=70, filler=1.0),
        _attempt(2, wpm=72, filler=1.0),
        _attempt(3, wpm=68, filler=1.0),
    ]
    top = narrative.select_top_priority([], slow)
    assert "pace" in top.lower() or "wpm" in top.lower()


def test_severe_grammar_still_wins_over_mild_disfluency():
    # rank-2 grammar beats a merely "notable" filler (rank 3).
    mild_filler = [
        _attempt(1, wpm=120, filler=4.2),
        _attempt(2, wpm=122, filler=4.1),
        _attempt(3, wpm=121, filler=4.0),
    ]
    top = narrative.select_top_priority([_gerund_pattern()], mild_filler)
    assert "gerund/infinitive confusion" in top


def test_silent_attempts_degrade_to_default():
    silent = [
        _attempt(1, wpm=0.0, filler=0.0, words=0),
        _attempt(2, wpm=0.0, filler=0.0, words=0),
        _attempt(3, wpm=0.0, filler=0.0, words=0),
    ]
    assert narrative.select_top_priority([_gerund_pattern()], silent) == narrative.SILENT_DEFAULT


def test_nothing_notable_degrades_to_sensible_default():
    assert narrative.select_top_priority([], GOOD_FLUENCY) == narrative.NOTABLE_DEFAULT


def test_narrative_describes_improvement():
    text = narrative.build_narrative(GOOD_FLUENCY, [_gerund_pattern()])
    assert "climbed" in text
    assert "116" in text and "138" in text
    assert "proceduralization" in text


def test_output_is_deterministic():
    patterns = [_gerund_pattern()]
    assert narrative.select_top_priority(patterns, GOOD_FLUENCY) == narrative.select_top_priority(
        patterns, GOOD_FLUENCY
    )
    assert narrative.build_narrative(GOOD_FLUENCY, patterns) == narrative.build_narrative(
        GOOD_FLUENCY, patterns
    )
