"""T057 — frontmatter emit matches contracts/report-frontmatter.yaml keys."""

from __future__ import annotations

from datetime import datetime

import pytest
import yaml

from speakloop.feedback import frontmatter

pytestmark = pytest.mark.unit


def _make_session(phase: str, patterns=None):
    return frontmatter.Session(
        session_id="2026-05-18-x",
        started_at=datetime(2026, 5, 18, 19, 14, 2),
        question_id="x",
        question_text="Explain how Kotlin coroutines differ from threads.\nNew line.",
        attempts=[
            frontmatter.Attempt(
                ordinal=i,
                time_budget_seconds=tb,
                actual_duration_seconds=tb - 1.5,
                metrics=frontmatter.AttemptMetrics(
                    words_total=100 * i,
                    speech_rate_wpm=110.0 + 5 * i,
                    filler_words_count=5,
                    filler_density_per_100_words=4.0,
                    pauses_count=10 - i,
                    mean_pause_ms=600.0,
                    self_corrections_count=2,
                ),
            )
            for i, tb in enumerate([240, 180, 120], start=1)
        ],
        grammar_patterns=patterns or [],
        generated_by_phase=phase,
    )


def test_phase_b_frontmatter_has_required_keys():
    s = _make_session("B")
    text = frontmatter.dump(s)
    assert text.startswith("---\n")
    assert text.endswith("---\n")

    parsed = yaml.safe_load(text.replace("---\n", "", 1).rstrip("---\n"))
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
        assert key in parsed
    assert parsed["schema_version"] == 1
    assert parsed["generated_by_phase"] == "B"
    assert parsed["grammar_patterns"] == []
    assert len(parsed["attempts"]) == 3


def test_phase_c_frontmatter_includes_patterns():
    s = _make_session(
        "C",
        patterns=[frontmatter.GrammarPattern(label="missing articles", occurrence_count=7)],
    )
    text = frontmatter.dump(s)
    parsed = yaml.safe_load(text.replace("---\n", "", 1).rstrip("---\n"))
    assert parsed["generated_by_phase"] == "C"
    assert parsed["grammar_patterns"][0]["label"] == "missing articles"


def test_per_attempt_metric_keys_match_data_model():
    s = _make_session("B")
    text = frontmatter.dump(s)
    parsed = yaml.safe_load(text.replace("---\n", "", 1).rstrip("---\n"))
    expected = {
        "words_total",
        "speech_rate_wpm",
        "filler_words_count",
        "filler_density_per_100_words",
        "pauses_count",
        "mean_pause_ms",
        "self_corrections_count",
    }
    assert set(parsed["attempts"][0]["metrics"].keys()) == expected


def test_question_renders_as_block_scalar():
    s = _make_session("B")
    text = frontmatter.dump(s)
    # PyYAML block scalar with `|` for multi-line question.
    assert "question: |" in text
