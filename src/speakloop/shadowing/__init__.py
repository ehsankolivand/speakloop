"""Answer shadowing — Mode B pure logic (018-self-practice-modes).

Splits a question's ideal answer into sentences (abbreviation-aware) and judges a learner's
spoken repeat for content-word completeness. Pure logic only — no engine import, deterministic
and offline.
"""

from __future__ import annotations

from speakloop.shadowing.judge import STRONG_COVERAGE, CompletenessResult, judge_completeness
from speakloop.shadowing.split import split_sentences

__all__ = [
    "split_sentences",
    "judge_completeness",
    "CompletenessResult",
    "STRONG_COVERAGE",
]
