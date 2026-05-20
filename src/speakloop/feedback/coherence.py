"""Deterministic ASR-garble (incoherence) evidence filter — FR-006.

Runs AFTER the analyzer's verbatim-substring check (FR-007): a quote that is a
real substring of a transcript may still be ASR garble (the documented
"Killing RT check"). This module is the offline, dependency-free guarantee that
such garble never reaches the report (research.md §e; Constitution Principle II).

Approach (no NLP dependency, fully deterministic):

* Tokenise the quote into lowercase word tokens.
* A token is *recognised* if it is in the shipped high-frequency wordlist
  (``common_words.txt``) OR is **attested** — i.e. the speaker used it at least
  twice across the three transcripts, so it is their real (technical) vocabulary
  rather than a one-off mishearing ("Kotlin", "coroutine", "dispatcher").
* Drop the quote when it has too few word tokens, or when the fraction of
  *unrecognised* tokens exceeds a threshold.

Bias: favour precision (FR-006). When in doubt, drop — a missing fix is better
than a fix anchored to garble.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path

from speakloop.asr import Transcript

WORDLIST_PATH = Path(__file__).parent / "common_words.txt"

# Tuning constants (documented; exercised by tests/unit/feedback/test_coherence.py).
# A coherent grammar-evidence phrase has at least this many word tokens.
MIN_WORD_TOKENS = 2
# Drop when strictly more than this fraction of word tokens are unrecognised.
# 0.25 tolerates one rare/proper word in a 4+ word phrase, but a 3-word phrase
# carrying one unattested non-word (e.g. "rt") is dropped — precision-first.
MAX_UNKNOWN_FRACTION = 0.25
# A token must recur at least this many times across the transcripts to count
# as the speaker's attested vocabulary (not a one-off ASR artefact).
ATTESTED_MIN_OCCURRENCES = 2

_WORD_RE = re.compile(r"[a-z]+(?:['\-][a-z]+)*")


def _tokens(text: str) -> list[str]:
    """Lowercase alphabetic word tokens (keeps internal apostrophes/hyphens)."""
    return _WORD_RE.findall(text.lower())


@lru_cache(maxsize=1)
def load_wordlist(path: Path = WORDLIST_PATH) -> frozenset[str]:
    """Load the high-frequency wordlist once. Blank lines and ``#`` comments are ignored."""
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        words.add(line)
    if not words:
        raise ValueError(f"coherence wordlist is empty: {path}")
    return frozenset(words)


def attested_terms(transcripts: Sequence[Transcript]) -> frozenset[str]:
    """Tokens the speaker used >= ATTESTED_MIN_OCCURRENCES times across attempts.

    These are treated as the speaker's real vocabulary (technical jargon a
    general wordlist will not contain) and are never counted as garble.
    """
    counts: Counter[str] = Counter()
    for t in transcripts:
        counts.update(_tokens(t.text))
    return frozenset(tok for tok, n in counts.items() if n >= ATTESTED_MIN_OCCURRENCES)


def _is_recognised(token: str, wordlist: frozenset[str], attested: frozenset[str]) -> bool:
    if token in wordlist or token in attested:
        return True
    # Possessive: "friend's" -> "friend".
    if token.endswith("'s") and token[:-2] in wordlist:
        return True
    # Contractions ("don't", "it's", "we're") are overwhelmingly coherent
    # English; ASR garble rarely carries an apostrophe.
    if "'" in token:
        return True
    # Hyphenated compound ("trade-offs", "real-time"): recognised if any part is.
    if "-" in token:
        parts = token.split("-")
        if any(p in wordlist or p in attested for p in parts):
            return True
    return False


def _coherent(quote: str, wordlist: frozenset[str], attested: frozenset[str]) -> bool:
    tokens = _tokens(quote)
    if len(tokens) < MIN_WORD_TOKENS:
        return False  # too few word tokens to be a coherent phrase
    unknown = sum(1 for t in tokens if not _is_recognised(t, wordlist, attested))
    return (unknown / len(tokens)) <= MAX_UNKNOWN_FRACTION


def make_filter(transcripts: Sequence[Transcript]) -> Callable[[str], bool]:
    """Return a ``quote -> bool`` predicate with attested terms precomputed.

    Use this in the analyzer hot path so attestation is computed once per
    session rather than once per quote.
    """
    wordlist = load_wordlist()
    attested = attested_terms(transcripts)
    return lambda quote: _coherent(quote, wordlist, attested)


def is_coherent(quote: str, transcripts: Sequence[Transcript]) -> bool:
    """True when ``quote`` reads as coherent English (FR-006).

    Convenience wrapper that computes attested terms from ``transcripts`` each
    call; prefer :func:`make_filter` when checking many quotes.
    """
    return _coherent(quote, load_wordlist(), attested_terms(transcripts))
