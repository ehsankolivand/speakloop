"""T022 — DebriefViewModel built from a Session (data-model §C)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from speakloop.debrief import view_model as vm
from speakloop.feedback import frontmatter

pytestmark = pytest.mark.unit


def _attempt(ordinal, *, wpm, filler, words=120, transcript="x") -> frontmatter.Attempt:
    return frontmatter.Attempt(
        ordinal=ordinal,
        time_budget_seconds={1: 240, 2: 180, 3: 120}[ordinal],
        actual_duration_seconds={1: 235.0, 2: 175.0, 3: 118.0}[ordinal],
        transcript=transcript,
        metrics=frontmatter.AttemptMetrics(
            words_total=words,
            speech_rate_wpm=wpm,
            filler_words_count=int(filler),
            filler_density_per_100_words=filler,
            pauses_count=5 - ordinal,
            mean_pause_ms=500.0,
            self_corrections_count=0,
        ),
    )


def _pattern(label, rank, occ, quote, corrected, *, extra=None) -> frontmatter.GrammarPattern:
    evidence = [{"attempt_ordinal": 1, "quote": quote, "corrected": corrected}]
    for q, c in extra or []:
        evidence.append({"attempt_ordinal": 2, "quote": q, "corrected": c})
    return frontmatter.GrammarPattern(
        label=label,
        occurrence_count=occ,
        evidence=evidence,
        explanation=f"because of {label}",
        impact_rank=rank,
        catalog_id=label,
    )


def _session(transcript="one two three four five six seven eight nine ten eleven twelve") -> frontmatter.Session:
    return frontmatter.Session(
        session_id="2026-05-20-demo",
        started_at=datetime(2026, 5, 20, 9, 0),
        question_id="demo",
        question_text="Q",
        attempts=[
            _attempt(1, wpm=116, filler=4.0, transcript=transcript),
            _attempt(2, wpm=128, filler=2.5, transcript="short answer"),
            _attempt(3, wpm=138, filler=1.5, transcript="another short one"),
        ],
        grammar_patterns=[
            # Deliberately out of order to test sorting by impact_rank.
            _pattern("plural/singular agreement", 3, 1, "eight year", "eight years"),
            _pattern("gerund/infinitive confusion", 2, 3, "I like to programming", "I like programming"),
        ],
        generated_by_phase="C",
        cross_attempt_narrative="Your speech rate climbed across the rounds.",
        top_priority="Fix gerund/infinitive confusion.",
    )


def test_trend_enums_map_correctly(tmp_path: Path):
    model = vm.build_view_model(_session(), sessions_dir=tmp_path)
    last = model.attempt_rows[-1]
    # WPM 116 → 138 (up beyond band) → improved.
    assert last.wpm_trend == vm.TrendDirection.IMPROVED
    # Filler 4.0 → 1.5 (down beyond band) → improved (lower is better).
    assert last.filler_trend == vm.TrendDirection.IMPROVED
    # Attempt 1 is the baseline → flat.
    assert model.attempt_rows[0].wpm_trend == vm.TrendDirection.FLAT
    assert model.attempt_rows[0].filler_trend == vm.TrendDirection.FLAT


def test_within_band_is_flat(tmp_path: Path):
    s = _session()
    # Make attempt 3 nearly identical to attempt 1 (within the tolerance band).
    s.attempts[2].metrics.speech_rate_wpm = 117.0  # |117-116| <= 5
    s.attempts[2].metrics.filler_density_per_100_words = 3.8  # |3.8-4.0| <= 0.5
    model = vm.build_view_model(s, sessions_dir=tmp_path)
    assert model.attempt_rows[-1].wpm_trend == vm.TrendDirection.FLAT
    assert model.attempt_rows[-1].filler_trend == vm.TrendDirection.FLAT


def test_worsened_trend(tmp_path: Path):
    s = _session()
    s.attempts[2].metrics.speech_rate_wpm = 90.0  # dropped from 116
    s.attempts[2].metrics.filler_density_per_100_words = 7.0  # rose from 4.0
    model = vm.build_view_model(s, sessions_dir=tmp_path)
    assert model.attempt_rows[-1].wpm_trend == vm.TrendDirection.WORSENED
    assert model.attempt_rows[-1].filler_trend == vm.TrendDirection.WORSENED


def test_transcript_preview_collapses_with_remaining_count(tmp_path: Path):
    model = vm.build_view_model(_session(), sessions_dir=tmp_path)
    p1 = model.transcript_previews[0]
    # 12 words → first 10 shown, 2 remaining.
    assert p1.preview == "one two three four five six seven eight nine ten"
    assert p1.remaining_words == 2
    assert p1.full_text.startswith("one two three")


def test_pattern_cards_sorted_by_impact_rank(tmp_path: Path):
    model = vm.build_view_model(_session(), sessions_dir=tmp_path)
    ranks = [c.impact_rank for c in model.pattern_cards]
    assert ranks == sorted(ranks)
    assert model.pattern_cards[0].label == "gerund/infinitive confusion"  # rank 2 first
    assert model.pattern_cards[0].you_said == "I like to programming"
    assert model.pattern_cards[0].better == "I like programming"


def test_audio_sections_order_and_count(tmp_path: Path):
    model = vm.build_view_model(_session(), sessions_dir=tmp_path)
    kinds = [s.kind for s in model.audio_sections]
    # narrative → top priority → one per pattern (2 patterns).
    assert kinds == [
        vm.AudioKind.NARRATIVE,
        vm.AudioKind.TOP_PRIORITY,
        vm.AudioKind.PATTERN,
        vm.AudioKind.PATTERN,
    ]
    assert model.audio_total == 4
    assert [s.index for s in model.audio_sections] == [1, 2, 3, 4]


def test_audio_never_includes_transcripts_or_metrics(tmp_path: Path):
    model = vm.build_view_model(_session(), sessions_dir=tmp_path)
    spoken = " ".join(s.speak_text for s in model.audio_sections)
    # Transcript text and raw metric numbers must never be read aloud (FR-017).
    assert "one two three four" not in spoken
    assert "116" not in spoken and "138" not in spoken


def test_is_first_time_only_when_no_prior_report(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    # Just this session's own file → first time.
    (sessions / "2026-05-20-demo.md").write_text("---\n---\n")
    assert vm.build_view_model(_session(), sessions_dir=sessions).is_first_time is True
    # A prior report exists → not first time.
    (sessions / "2026-05-19-old.md").write_text("---\n---\n")
    assert vm.build_view_model(_session(), sessions_dir=sessions).is_first_time is False


def test_grammar_available_reflects_phase(tmp_path: Path):
    s = _session()
    s.generated_by_phase = "B"
    s.grammar_patterns = []
    model = vm.build_view_model(s, sessions_dir=tmp_path)
    assert model.grammar_available is False
    assert model.pattern_cards == []


def test_transcripts_collapsed_on_entry(tmp_path: Path):
    model = vm.build_view_model(_session(), sessions_dir=tmp_path)
    assert model.transcripts_expanded is False
