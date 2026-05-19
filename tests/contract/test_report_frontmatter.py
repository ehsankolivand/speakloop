"""Contract test for the report frontmatter schema example."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.contract

CONTRACT_PATH = (
    Path(__file__).parents[2]
    / "specs"
    / "001-v1-product-spec"
    / "contracts"
    / "report-frontmatter.yaml"
)

PER_ATTEMPT_METRIC_KEYS = {
    "words_total",
    "speech_rate_wpm",
    "filler_words_count",
    "filler_density_per_100_words",
    "pauses_count",
    "mean_pause_ms",
    "self_corrections_count",
}


def test_report_frontmatter_example_matches_contract():
    with open(CONTRACT_PATH) as f:
        doc = yaml.safe_load(f)

    for key in (
        "schema_version",
        "session_id",
        "started_at",
        "question_id",
        "question",
        "attempts",
        "grammar_patterns",
        "generated_by_phase",
    ):
        assert key in doc, f"missing required frontmatter key: {key}"

    assert doc["schema_version"] == 1
    assert isinstance(doc["attempts"], list)
    assert len(doc["attempts"]) == 3

    for attempt in doc["attempts"]:
        assert "ordinal" in attempt
        assert "time_budget_seconds" in attempt
        assert "actual_duration_seconds" in attempt
        assert set(attempt["metrics"].keys()) == PER_ATTEMPT_METRIC_KEYS

    assert doc["generated_by_phase"] in {"A", "B", "C"}
