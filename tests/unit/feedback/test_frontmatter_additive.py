"""T007 — additive frontmatter round-trip (schema_version stays 1).

The 002 feature adds optional fields to GrammarPattern (explanation, impact_rank,
catalog_id), a per-evidence `corrected`, and two top-level keys
(cross_attempt_narrative, top_priority). All are additive: a Session carrying
them must serialize and re-parse identically, and a pre-feature report (none of
the new keys) must still parse. `schema_version` MUST remain 1.
"""

from __future__ import annotations

from datetime import datetime

import pytest
import yaml

from speakloop.feedback import frontmatter

pytestmark = pytest.mark.unit


def _session_with_new_fields() -> frontmatter.Session:
    return frontmatter.Session(
        session_id="2026-05-20-kotlin",
        started_at=datetime(2026, 5, 20, 9, 30, 0),
        question_id="kotlin",
        question_text="Explain Kotlin coroutines.\nSecond line.",
        attempts=[
            frontmatter.Attempt(
                ordinal=i,
                time_budget_seconds=tb,
                actual_duration_seconds=tb - 2.0,
                metrics=frontmatter.AttemptMetrics(
                    words_total=90 * i,
                    speech_rate_wpm=110.0 + 10 * i,
                    filler_words_count=4,
                    filler_density_per_100_words=4.0 - i,
                    pauses_count=8 - i,
                    mean_pause_ms=550.0,
                    self_corrections_count=1,
                ),
            )
            for i, tb in enumerate([240, 180, 120], start=1)
        ],
        grammar_patterns=[
            frontmatter.GrammarPattern(
                label="gerund/infinitive confusion",
                occurrence_count=3,
                evidence=[
                    {
                        "attempt_ordinal": 1,
                        "quote": "I like to programming",
                        "corrected": "I like programming",
                    }
                ],
                explanation="Persian does not split verbs into -ing vs to complements.",
                impact_rank=2,
                catalog_id="gerund-infinitive-confusion",
            ),
        ],
        generated_by_phase="C",
        cross_attempt_narrative="Speech rate climbed from 116 to 138 WPM.\nArticles stayed inconsistent.",
        top_priority='Fix gerund/infinitive: say "I like programming".',
    )


def test_new_fields_round_trip_identically():
    session = _session_with_new_fields()
    text = frontmatter.dump(session)

    reparsed = frontmatter.parse(text)
    # dump → parse → dump is idempotent at the serialized level.
    assert frontmatter.dump(reparsed) == text

    # And the additive fields survive a single parse.
    p = reparsed.grammar_patterns[0]
    assert p.label == "gerund/infinitive confusion"
    assert p.impact_rank == 2
    assert p.catalog_id == "gerund-infinitive-confusion"
    assert p.explanation.startswith("Persian does not split")
    assert p.evidence[0]["quote"] == "I like to programming"
    assert p.evidence[0]["corrected"] == "I like programming"
    assert reparsed.cross_attempt_narrative.startswith("Speech rate climbed")
    assert reparsed.top_priority.startswith("Fix gerund/infinitive")
    assert reparsed.generated_by_phase == "C"


def test_schema_version_stays_one():
    text = frontmatter.dump(_session_with_new_fields())
    parsed_yaml = yaml.safe_load(text.split("---\n", 2)[1])
    assert parsed_yaml["schema_version"] == 1


def test_pre_feature_report_still_parses():
    # A report written before this feature: no impact_rank / catalog_id /
    # explanation / corrected / cross_attempt_narrative / top_priority.
    legacy = (
        "---\n"
        "schema_version: 1\n"
        "session_id: 2026-04-01-old\n"
        "started_at: '2026-04-01T08:00:00'\n"
        "question_id: old\n"
        "question: |\n"
        "  Legacy question.\n"
        "attempts:\n"
        "  - ordinal: 1\n"
        "    time_budget_seconds: 240\n"
        "    actual_duration_seconds: 230.0\n"
        "    metrics:\n"
        "      words_total: 100\n"
        "      speech_rate_wpm: 120.0\n"
        "      filler_words_count: 3\n"
        "      filler_density_per_100_words: 3.0\n"
        "      pauses_count: 5\n"
        "      mean_pause_ms: 500.0\n"
        "      self_corrections_count: 1\n"
        "grammar_patterns:\n"
        "  - label: missing articles\n"
        "    occurrence_count: 7\n"
        "    suggested_fix: Add a/an/the before singular count nouns.\n"
        "generated_by_phase: C\n"
        "---\n"
        "# Old report body\n"
    )
    session = frontmatter.parse(legacy)
    assert session.session_id == "2026-04-01-old"
    assert session.generated_by_phase == "C"
    assert len(session.attempts) == 1
    assert session.attempts[0].metrics.words_total == 100
    # New fields default to empty — never crash on a pre-feature report.
    assert session.cross_attempt_narrative is None
    assert session.top_priority is None
    pat = session.grammar_patterns[0]
    assert pat.label == "missing articles"
    assert pat.impact_rank is None
    assert pat.catalog_id is None
    assert pat.explanation is None


def test_unknown_keys_are_ignored():
    text_with_extra = (
        "---\n"
        "schema_version: 1\n"
        "session_id: x\n"
        "started_at: '2026-05-20T09:00:00'\n"
        "question_id: x\n"
        "question: |\n"
        "  Q.\n"
        "attempts: []\n"
        "grammar_patterns: []\n"
        "generated_by_phase: B\n"
        "future_field_we_dont_know: 42\n"
        "---\n"
    )
    session = frontmatter.parse(text_with_extra)  # must not raise
    assert session.generated_by_phase == "B"
    assert session.attempts == []
