"""Answer-Quality Grade (010-interview-loop, P2b).

A per-question, per-session band — poor / fair / good / strong — that drives the
spaced-repetition schedule. Primary signal is content coverage (P3); when coverage
is unavailable (P3 not active, or analysis could not run) the grade falls back to
grammar severity + fluency only, so scheduling still works without P3 (FR-010).

Pure logic — no LLM, no engine, stdlib only. Bands match the spec Key Definitions;
the exact coverage boundaries are the confirmed defaults (clarifications) and are
the single place to tune them.
"""

from __future__ import annotations

from typing import Literal

Grade = Literal["poor", "fair", "good", "strong"]

# Coverage-band boundaries (aggregate = (covered + 0.5*partial) / N).
POOR_MAX = 0.50  # below this (or any content error) → poor
FAIR_MAX = 0.75
GOOD_MAX = 0.95  # at/above → strong (if clean)

# Grammar-severity proxy: total occurrences across patterns this session.
LOW_GRAMMAR_OCCURRENCES = 2  # <= this counts as "low grammar severity"


def _grammar_occurrences(grammar_patterns) -> int:
    total = 0
    for p in grammar_patterns or []:
        # accept either GrammarPattern objects or plain dicts
        count = getattr(p, "occurrence_count", None)
        if count is None and isinstance(p, dict):
            count = p.get("occurrence_count", 0)
        total += int(count or 0)
    return total


def grade_session(
    *,
    coverage_aggregate: float | None,
    content_error_count: int = 0,
    grammar_patterns=None,
) -> Grade:
    """Return the answer-quality grade for one session.

    ``coverage_aggregate`` is the session's final-round aggregate coverage in
    [0, 1], or ``None`` when coverage was not computed (→ fallback path).
    """
    occurrences = _grammar_occurrences(grammar_patterns)

    if coverage_aggregate is not None:
        if coverage_aggregate < POOR_MAX or content_error_count > 0:
            return "poor"
        if coverage_aggregate < FAIR_MAX:
            return "fair"
        if coverage_aggregate < GOOD_MAX:
            return "good"
        # near-complete coverage, no content errors → strong only if grammar is clean
        return "strong" if occurrences <= LOW_GRAMMAR_OCCURRENCES else "good"

    # Fallback (no coverage): grade from grammar severity alone (FR-010).
    if occurrences == 0:
        return "strong"
    if occurrences <= LOW_GRAMMAR_OCCURRENCES:
        return "good"
    if occurrences <= 5:
        return "fair"
    return "poor"
