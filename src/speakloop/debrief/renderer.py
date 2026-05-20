"""In-place `rich` renderer for the debrief (FR-010..FR-014, research.md §c).

Builds composed `rich` renderables from a :class:`DebriefViewModel` — a bordered
Top-priority banner (FR-011), three-line pattern cards (FR-012), a trend-coloured
attempt table (FR-013), and collapsed transcripts with a "+N words" indicator
(FR-014). A ``highlight_ref`` emphasises the section currently being read aloud
and an "X of N sections" progress line is shown while audio plays (FR-019, US3).

Driven by :class:`rich.live.Live` so the same view repaints in place as the
highlight advances; falls back to a single ``console.print`` when the terminal
reports no control capability.
"""

from __future__ import annotations

from rich import box
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from speakloop.debrief.view_model import DebriefViewModel, TrendDirection

# Exact user-facing strings (asserted by tests / T034 / T035 / T040).
GRAMMAR_UNAVAILABLE_LINE = (
    "Grammar pattern analysis is available when the LLM model is installed."
)
NO_PATTERNS_LINE = "No actionable grammar patterns detected this session."
FIRST_TIME_LINE = (
    "This is your feedback. I'll read the key parts aloud, then you can replay "
    "this question or pick a new one."
)

# Trend → colour (FR-013). Filler "improved" already means the value went down,
# so a green filler cell correctly reads as good.
_TREND_STYLE = {
    TrendDirection.IMPROVED: "green",
    TrendDirection.FLAT: "yellow",
    TrendDirection.WORSENED: "red",
}
_TREND_ARROW = {
    TrendDirection.IMPROVED: "↑",
    TrendDirection.FLAT: "→",
    TrendDirection.WORSENED: "↓",
}

_DEFAULT_BORDER = "grey50"
_HIGHLIGHT_BORDER = "bold magenta"


def trend_style(direction: TrendDirection) -> str:
    return _TREND_STYLE[direction]


def _border(highlight_ref: str | None, this_ref: str) -> str:
    return _HIGHLIGHT_BORDER if highlight_ref == this_ref else _DEFAULT_BORDER


def _title(highlight_ref: str | None, this_ref: str, label: str) -> str:
    return f"▶ {label}" if highlight_ref == this_ref else label


def _narrative_panel(model: DebriefViewModel, highlight_ref: str | None) -> Panel:
    return Panel(
        Text(model.narrative or "—"),
        title=_title(highlight_ref, "narrative", "How it went"),
        border_style=_border(highlight_ref, "narrative"),
        box=box.ROUNDED,
    )


def _top_priority_banner(model: DebriefViewModel, highlight_ref: str | None) -> Panel:
    return Panel(
        Text(model.top_priority or "—", style="bold"),
        title=_title(highlight_ref, "top_priority", "★ Top priority for next session"),
        border_style=(
            _HIGHLIGHT_BORDER if highlight_ref == "top_priority" else "bold yellow"
        ),
        box=box.DOUBLE,
    )


def _attempt_table(model: DebriefViewModel) -> Table:
    table = Table(title="Attempt-by-attempt", box=box.SIMPLE_HEAVY, expand=False)
    table.add_column("Round", justify="right")
    table.add_column("Budget", justify="right")
    table.add_column("Used", justify="right")
    table.add_column("WPM", justify="right")
    table.add_column("Fillers/100w", justify="right")
    table.add_column("Pauses", justify="right")
    for row in model.attempt_rows:
        wpm = Text(f"{row.wpm:.0f} {_TREND_ARROW[row.wpm_trend]}", style=trend_style(row.wpm_trend))
        fillers = Text(
            f"{row.filler_density:.1f} {_TREND_ARROW[row.filler_trend]}",
            style=trend_style(row.filler_trend),
        )
        table.add_row(
            str(row.ordinal), row.budget, row.used, wpm, fillers, str(row.pauses)
        )
    return table


def _pattern_card(card, index: int, highlight_ref: str | None) -> Panel:
    body = Text()
    if card.you_said:
        body.append("You said:  ", style="bold")
        body.append(f"“{card.you_said}”\n")
    if card.better and card.better != card.you_said:
        body.append("Better:    ", style="bold green")
        body.append(f"“{card.better}”\n")
    if card.because:
        body.append("Because:   ", style="bold cyan")
        body.append(card.because)
    for q, c in card.extra_evidence:
        if q and c and c != q:
            body.append(f"\n  • “{q}” → “{c}”", style="dim")
        elif q:
            body.append(f"\n  • “{q}”", style="dim")
    label = f"{card.label}  ·  impact rank {card.impact_rank}"
    return Panel(
        body,
        title=_title(highlight_ref, f"pattern:{index}", label),
        border_style=_border(highlight_ref, f"pattern:{index}"),
        box=box.ROUNDED,
    )


def _grammar_section(model: DebriefViewModel, highlight_ref: str | None) -> RenderableType:
    if not model.grammar_available:
        return Panel(
            Text(GRAMMAR_UNAVAILABLE_LINE, style="dim italic"),
            title="Grammar patterns",
            border_style=_DEFAULT_BORDER,
            box=box.ROUNDED,
        )
    if not model.pattern_cards:
        return Panel(
            Text(NO_PATTERNS_LINE, style="dim italic"),
            title="Grammar patterns",
            border_style=_DEFAULT_BORDER,
            box=box.ROUNDED,
        )
    cards = [_pattern_card(c, i, highlight_ref) for i, c in enumerate(model.pattern_cards)]
    return Group(*cards)


def _transcripts_panel(model: DebriefViewModel) -> Panel:
    body = Text()
    for i, p in enumerate(model.transcript_previews):
        if i:
            body.append("\n")
        body.append(f"Attempt {p.ordinal}: ", style="bold")
        if model.transcripts_expanded:
            body.append(p.full_text or "(silent)")
        else:
            body.append(p.preview or "(silent)")
            if p.remaining_words:
                body.append(f"  (+{p.remaining_words} words)", style="dim")
    hint = "press t to collapse" if model.transcripts_expanded else "press t to expand"
    return Panel(
        body,
        title=f"Transcripts [dim]({hint})[/dim]",
        border_style=_DEFAULT_BORDER,
        box=box.ROUNDED,
    )


def supports_live(console: Console) -> bool:
    """True when the terminal can repaint in place; else use a plain print."""
    return console.is_terminal


class DebriefRenderer:
    """Builds (and, with :meth:`live`, animates) the debrief view."""

    def __init__(self, model: DebriefViewModel, *, console: Console | None = None) -> None:
        self.model = model
        self.console = console or Console()

    def build(
        self, *, highlight_ref: str | None = None, progress_text: str | None = None
    ) -> RenderableType:
        parts: list[RenderableType] = []
        if self.model.is_first_time:
            parts.append(Text(FIRST_TIME_LINE, style="italic cyan"))
        if self.model.narrative:
            parts.append(_narrative_panel(self.model, highlight_ref))
        parts.append(_top_priority_banner(self.model, highlight_ref))
        parts.append(_attempt_table(self.model))
        parts.append(_grammar_section(self.model, highlight_ref))
        parts.append(_transcripts_panel(self.model))
        if progress_text:
            parts.append(Text(progress_text, style="bold cyan"))
        return Group(*parts)

    def print_static(
        self, *, highlight_ref: str | None = None, progress_text: str | None = None
    ) -> None:
        """One-shot render (the plain fallback / US2 no-audio path)."""
        self.console.print(self.build(highlight_ref=highlight_ref, progress_text=progress_text))

    def live(self) -> Live:
        """A `Live` bound to this console for animated highlight updates (US3)."""
        return Live(
            self.build(),
            console=self.console,
            auto_refresh=False,
            transient=False,
        )
