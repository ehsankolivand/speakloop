"""T013 — deterministic ASR-garble coherence filter (FR-006, research.md §e).

The documented garble "Killing RT check" must be dropped; the speaker's attested
technical vocabulary ("Kotlin", "coroutine", "dispatcher") must be kept; a clean
grammatical quote passes; ambiguous fragments are dropped (precision-first).
"""

from __future__ import annotations

import pytest

from speakloop.asr import Transcript
from speakloop.feedback import coherence

pytestmark = pytest.mark.unit


def _transcripts() -> list[Transcript]:
    # "kotlin", "coroutine", "dispatcher" each occur >= 2 times across attempts,
    # so they are attested (kept) even though they are not in the wordlist.
    # "rt" occurs only once (inside the garble), so it stays unrecognised.
    return [
        Transcript(
            text="I use Kotlin every day. A coroutine runs on a dispatcher. Killing RT check.",
            audio_duration_seconds=10.0,
        ),
        Transcript(
            text="Kotlin is great. The coroutine suspends. The dispatcher schedules the work.",
            audio_duration_seconds=10.0,
        ),
        Transcript(text="He writes clean code every day.", audio_duration_seconds=5.0),
    ]


def test_garble_is_dropped():
    assert coherence.is_coherent("Killing RT check", _transcripts()) is False


def test_attested_jargon_is_kept():
    ts = _transcripts()
    # All three jargon terms are attested across attempts → coherent.
    assert coherence.is_coherent("a coroutine runs on a dispatcher", ts) is True
    assert coherence.is_coherent("I use Kotlin every day", ts) is True


def test_clean_grammatical_quote_passes():
    assert coherence.is_coherent("He writes clean code", _transcripts()) is True
    # A short but coherent grammar-evidence phrase (3sg-s drop) survives.
    assert coherence.is_coherent("he write a function", _transcripts()) is True


def test_ambiguous_fragment_is_dropped():
    # Two non-words, no attestation → 100% unknown → dropped.
    assert coherence.is_coherent("zogzog plonk", _transcripts()) is False


def test_single_token_is_too_short():
    # Even an attested term alone is too little context to be evidence.
    assert coherence.is_coherent("dispatcher", _transcripts()) is False


def test_attestation_requires_two_occurrences():
    # "widget" appears exactly once → not attested → treated as unknown.
    once = [
        Transcript(text="The widget broke today.", audio_duration_seconds=3.0),
        Transcript(text="He writes clean code.", audio_duration_seconds=3.0),
    ]
    attested = coherence.attested_terms(once)
    assert "widget" not in attested
    # 1 unknown ("widget") of 3 tokens = 0.33 > 0.25 → dropped.
    assert coherence.is_coherent("the widget broke", once) is False


def test_make_filter_matches_is_coherent():
    ts = _transcripts()
    predicate = coherence.make_filter(ts)
    for quote in ("Killing RT check", "a coroutine runs on a dispatcher", "He writes clean code"):
        assert predicate(quote) == coherence.is_coherent(quote, ts)


def test_wordlist_loads_and_excludes_garble_tokens():
    words = coherence.load_wordlist()
    assert "the" in words and "code" in words and "programming" in words
    # The garble token must NOT be in the shipped wordlist (would defeat FR-006).
    assert "rt" not in words
