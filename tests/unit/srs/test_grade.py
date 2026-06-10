"""Answer-quality grade tests (010-interview-loop, T052) — table-driven."""

from __future__ import annotations

import pytest

from speakloop.srs.grade import grade_session

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("aggregate", "content_errors", "occurrences", "expected"),
    [
        # coverage-primary bands
        (0.30, 0, 0, "poor"),
        (0.49, 0, 0, "poor"),
        (0.95, 1, 0, "poor"),     # any content error → poor regardless of coverage
        (0.50, 0, 0, "fair"),
        (0.74, 0, 0, "fair"),
        (0.75, 0, 0, "good"),
        (0.94, 0, 0, "good"),
        (1.00, 0, 0, "strong"),
        (1.00, 0, 5, "good"),     # complete coverage but noisy grammar → good, not strong
        # fallback (coverage None): grammar severity only
        (None, 0, 0, "strong"),
        (None, 0, 2, "good"),
        (None, 0, 4, "fair"),
        (None, 0, 9, "poor"),
    ],
)
def test_grade_bands(aggregate, content_errors, occurrences, expected):
    patterns = [{"occurrence_count": occurrences}] if occurrences else []
    assert grade_session(
        coverage_aggregate=aggregate,
        content_error_count=content_errors,
        grammar_patterns=patterns,
    ) == expected
