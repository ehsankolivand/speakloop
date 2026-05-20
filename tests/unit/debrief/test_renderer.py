"""T024 — debrief renderer output (FR-011..FR-014, FR-028, FR-030)."""

from __future__ import annotations

import pytest
from rich.console import Console

from speakloop.debrief import renderer
from speakloop.debrief.renderer import DebriefRenderer
from speakloop.debrief.view_model import (
    AttemptRow,
    AudioKind,
    AudioSection,
    DebriefViewModel,
    PatternCard,
    TranscriptPreview,
    TrendDirection,
)

pytestmark = pytest.mark.unit


def _model(*, is_first_time=False, grammar_available=True, with_patterns=True) -> DebriefViewModel:
    rows = [
        AttemptRow(1, "4:00", "3:55", 116, 4.0, 4, TrendDirection.FLAT, TrendDirection.FLAT),
        AttemptRow(2, "3:00", "2:55", 100, 6.0, 3, TrendDirection.WORSENED, TrendDirection.WORSENED),
        AttemptRow(3, "2:00", "1:55", 140, 1.5, 2, TrendDirection.IMPROVED, TrendDirection.IMPROVED),
    ]
    cards = (
        [
            PatternCard(
                label="gerund/infinitive confusion",
                impact_rank=2,
                you_said="I like to programming",
                better="I like programming",
                because="Persian does not split verbs into -ing vs to complements.",
            )
        ]
        if with_patterns
        else []
    )
    previews = [TranscriptPreview(1, "one two three four five six seven eight nine ten", 5, "full text here")]
    return DebriefViewModel(
        is_first_time=is_first_time,
        top_priority="Fix gerund/infinitive confusion: say I like programming.",
        narrative="Your speech rate climbed across the rounds.",
        attempt_rows=rows,
        pattern_cards=cards,
        transcript_previews=previews,
        grammar_available=grammar_available,
        audio_sections=[AudioSection(AudioKind.NARRATIVE, 1, "x", "narrative")],
    )


def _text(renderable, width=200) -> str:
    console = Console(width=width, record=True, force_terminal=True)
    console.print(renderable)
    return console.export_text()


def _colors(renderable, width=200) -> set[str]:
    console = Console(width=width, force_terminal=True, color_system="standard")
    colors: set[str] = set()
    for seg in console.render(renderable, console.options):
        if seg.style and seg.style.color and seg.style.color.name:
            colors.add(seg.style.color.name)
    return colors


def test_top_priority_banner_present_and_distinct():
    text = _text(DebriefRenderer(_model()).build())
    assert "Top priority for next session" in text
    assert "Fix gerund/infinitive confusion" in text


def test_pattern_card_three_lines_in_order():
    text = _text(DebriefRenderer(_model()).build())
    i_you = text.find("You said:")
    i_better = text.find("Better:")
    i_because = text.find("Because:")
    assert -1 < i_you < i_better < i_because


def test_trend_cells_coloured_per_direction():
    table_colors = _colors(renderer._attempt_table(_model()))
    assert "green" in table_colors  # an improved metric
    assert "red" in table_colors  # a worsened metric


def test_trend_style_mapping():
    assert renderer.trend_style(TrendDirection.IMPROVED) == "green"
    assert renderer.trend_style(TrendDirection.FLAT) == "yellow"
    assert renderer.trend_style(TrendDirection.WORSENED) == "red"


def test_transcript_collapsed_shows_preview_and_remaining():
    text = _text(DebriefRenderer(_model()).build())
    assert "one two three four five" in text
    assert "+5 words" in text


def test_transcript_expanded_shows_full_text():
    model = _model()
    model.transcripts_expanded = True
    text = _text(DebriefRenderer(model).build())
    assert "full text here" in text


def test_grammar_unavailable_placeholder():
    text = _text(DebriefRenderer(_model(grammar_available=False, with_patterns=False)).build())
    assert renderer.GRAMMAR_UNAVAILABLE_LINE in text


def test_no_actionable_patterns_line():
    text = _text(DebriefRenderer(_model(grammar_available=True, with_patterns=False)).build())
    assert renderer.NO_PATTERNS_LINE in text


def test_first_time_line_appears_only_when_flagged():
    assert "This is your feedback." in _text(DebriefRenderer(_model(is_first_time=True)).build())
    assert "This is your feedback." not in _text(DebriefRenderer(_model(is_first_time=False)).build())


def test_highlight_marks_the_active_section():
    # The highlighted section title is prefixed with ▶.
    text = _text(DebriefRenderer(_model()).build(highlight_ref="top_priority"))
    assert "▶" in text


def test_progress_text_rendered_when_provided():
    text = _text(DebriefRenderer(_model()).build(progress_text="🔊 2 of 4 sections — press any key to skip"))
    assert "2 of 4 sections" in text
