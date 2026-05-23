"""V-R1 / V-R2 / V-R3 — report invariance (contracts/report-invariance.md).

The sprint changes content quality, never the report the user sees:
- V-R1: the body section set + order are unchanged (no section added/removed).
- V-R2: frontmatter dump→parse→dump is idempotent and schema_version stays 1.
- V-R3: a pre-feature-style report and a post-feature CLEAN report differ only in
  CONTENT — identical frontmatter key set, section set, and ordering (empty
  structural diff); no new feedback dimension/section (FR-015).
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from speakloop.feedback import frontmatter, report_builder
from speakloop.feedback.frontmatter import (
    Attempt,
    AttemptMetrics,
    GrammarPattern,
    Session,
)

pytestmark = pytest.mark.unit

# The fixed, user-visible body sections (report_builder.build) — adding or removing
# one is a structural change this sprint forbids (I3, FR-015, SC-005).
EXPECTED_SECTIONS = [
    "## Top priority for next session",
    "## Attempt-by-attempt summary",
    "## Cross-attempt comparison",
    "## Grammar patterns",
    "## Transcripts",
]


def _metrics(wpm, fill, words=120):
    return AttemptMetrics(
        words_total=words,
        speech_rate_wpm=wpm,
        filler_words_count=int(fill),
        filler_density_per_100_words=fill,
        pauses_count=3,
        mean_pause_ms=500.0,
        self_corrections_count=0,
    )


def _attempt(ordinal, wpm, fill, text):
    return Attempt(
        ordinal=ordinal,
        time_budget_seconds={1: 240, 2: 180, 3: 120}[ordinal],
        actual_duration_seconds=100.0,
        transcript=text,
        metrics=_metrics(wpm, fill),
    )


def _session(*, patterns, narrative, top_priority):
    return Session(
        session_id="2026-05-22-q01",
        started_at=datetime(2026, 5, 22, 10, 0, 0),
        question_id="q01",
        question_text="Tell me about a system you designed.",
        attempts=[
            _attempt(1, 116, 2.5, "I like to programming and I have eight year experience."),
            _attempt(2, 128, 2.0, "I build payment systems for a fintech company."),
            _attempt(3, 138, 1.5, "Honestly I enjoy building reliable services."),
        ],
        grammar_patterns=patterns,
        generated_by_phase="C",
        cross_attempt_narrative=narrative,
        top_priority=top_priority,
    )


def _sections(body: str) -> list[str]:
    return [ln.strip() for ln in body.splitlines() if ln.startswith("## ")]


def _gerund():
    return GrammarPattern(
        label="gerund/infinitive confusion",
        occurrence_count=2,
        evidence=[{"attempt_ordinal": 1, "quote": "like to programming", "corrected": "like programming"}],
        explanation="Persian does not split verbs into -ing vs to complements.",
        impact_rank=2,
        catalog_id="gerund-infinitive-confusion",
    )


# --- V-R1: section set + order ------------------------------------------------


def test_section_set_and_order_unchanged():
    report = report_builder.build(_session(patterns=[_gerund()], narrative="N", top_priority="T"))
    assert _sections(report) == EXPECTED_SECTIONS


def test_no_new_feedback_dimension():
    report = report_builder.build(_session(patterns=[_gerund()], narrative="N", top_priority="T")).lower()
    # FR-015 / I7: no ideal-answer / semantic-equivalence / scoring dimension crept in.
    for forbidden in ("ideal answer", "semantic", "model answer", "## score", "similarity"):
        assert forbidden not in report


# --- V-R2: frontmatter round-trip + schema_version ---------------------------


def test_schema_version_is_one_and_not_bumped():
    assert frontmatter.SCHEMA_VERSION == 1
    dumped = frontmatter.dump(_session(patterns=[_gerund()], narrative="N", top_priority="T"))
    assert "schema_version: 1" in dumped
    assert "schema_version: 2" not in dumped


def test_dump_parse_dump_is_idempotent():
    s = _session(patterns=[_gerund()], narrative="Across the rounds pace climbed.", top_priority="Fix gerunds.")
    d1 = frontmatter.dump(s)
    d2 = frontmatter.dump(frontmatter.parse(d1))
    d3 = frontmatter.dump(frontmatter.parse(d2))
    assert d2 == d3  # serialized round-trip is stable
    assert "schema_version: 1" in d2


# --- V-R3: pre vs post CLEAN report — structural diff is empty ---------------


def test_pre_and_post_clean_reports_have_identical_structure():
    # "pre-feature" content: a single raw-ish pattern, terse narrative.
    pre = _session(
        patterns=[_gerund()],
        narrative="Your speech rate held steady at from 116 to 138 WPM.",  # old-style wording
        top_priority='Fix gerund/infinitive confusion: say "like programming".',
    )
    # "post-feature" CLEAN content: deduped/tightened narrative, better correction.
    post = _session(
        patterns=[_gerund()],
        narrative="Across the timed rounds your speech rate climbed from 116 to 138 WPM.",
        top_priority='Fix gerund/infinitive confusion: say "like programming", not "like to programming".',
    )
    pre_report = report_builder.build(pre)
    post_report = report_builder.build(post)

    # Section set + order identical (structure), even though content differs.
    assert _sections(pre_report) == _sections(post_report) == EXPECTED_SECTIONS
    # Frontmatter top-level key set + order identical.
    pre_keys = re.findall(r"^([a-z_]+):", frontmatter.dump(pre), flags=re.MULTILINE)
    post_keys = re.findall(r"^([a-z_]+):", frontmatter.dump(post), flags=re.MULTILINE)
    assert pre_keys == post_keys
    # And the content really did differ (so the test isn't trivially comparing equals).
    assert pre_report != post_report
