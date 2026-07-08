"""Content-word completeness judge for answer shadowing (018, US2, FR-034).

Deterministic, offline scoring of a learner's spoken repeat against the target sentence: which of
the sentence's KEY content words (tokens minus English function words) appeared in the repeat, and
which were missed. Mirrors the warm-up judge's normalization (`[A-Za-z0-9']+`, lowercased). No
model in the loop → identical output for a fixed transcript (SC-008).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[A-Za-z0-9']+")

# English function words excluded from "content words" (articles, pronouns, prepositions,
# conjunctions, auxiliaries, common determiners). A learner need not echo these to be "complete".
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "if", "so", "than", "then", "as", "of", "to", "in",
        "on", "at", "by", "for", "with", "from", "into", "onto", "over", "under", "about", "after",
        "before", "between", "through", "during", "without", "within", "up", "out", "off", "down",
        "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did", "done",
        "has", "have", "had", "will", "would", "shall", "should", "can", "could", "may", "might",
        "must", "not", "no", "nor", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their", "this", "that", "these", "those",
        "there", "here", "which", "who", "whom", "whose", "what", "when", "where", "why", "how",
        "any", "some", "all", "each", "both", "more", "most", "such", "only", "very", "just", "also",
    }
)

# The CLI flags a sentence as "strong" at/above this coverage; nothing blocks progress (FR-034).
STRONG_COVERAGE = 0.70


@dataclass(frozen=True)
class CompletenessResult:
    content_words: tuple[str, ...]  # key words of the sentence (deduped, in order)
    covered: tuple[str, ...]  # content words present in the repeat
    missed: tuple[str, ...]  # content words absent from the repeat
    coverage: float  # len(covered) / len(content_words); 0.0 when there are none
    captured: bool  # False when the repeat is empty/whitespace ("not captured")

    @property
    def is_strong(self) -> bool:
        return self.captured and self.coverage >= STRONG_COVERAGE


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text or "")]


def judge_completeness(sentence: str, repeat_text: str) -> CompletenessResult:
    """Judge how completely ``repeat_text`` reproduced the content words of ``sentence``."""
    content = [t for t in dict.fromkeys(_tokens(sentence)) if t not in _STOPWORDS]
    repeat = set(_tokens(repeat_text))
    captured = bool(repeat)

    if not content:
        # a sentence of only function words is trivially "complete" when anything was said
        return CompletenessResult((), (), (), 1.0 if captured else 0.0, captured)

    covered = tuple(w for w in content if w in repeat)
    missed = tuple(w for w in content if w not in repeat)
    return CompletenessResult(
        content_words=tuple(content),
        covered=covered,
        missed=missed,
        coverage=len(covered) / len(content),
        captured=captured,
    )
