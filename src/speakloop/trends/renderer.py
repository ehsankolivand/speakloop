"""Render a TrendsSummary to the terminal via rich."""

from __future__ import annotations

import io

from rich.console import Console
from rich.table import Table

from speakloop.trends.aggregator import (
    METRIC_HIGHER_IS_BETTER,
    METRIC_LABELS,
    TrendsSummary,
    format_series,
)


def _delta_cell(name: str, delta: float) -> str:
    """The Δ cell: the signed change plus a direction word, since a bare ``+2.0`` is ambiguous
    (fewer fillers/pauses is an improvement even though the number fell). Colour is a bonus in a
    real terminal; the word survives the plain-text capture the tests read (IMP-042)."""
    if delta == 0:
        return f"{delta:+.1f}"
    improved = (delta > 0) == METRIC_HIGHER_IS_BETTER.get(name, True)
    word, colour = ("better", "green") if improved else ("worse", "red")
    return f"[{colour}]{delta:+.1f} ({word})[/{colour}]"


def render(summary: TrendsSummary, *, console: Console | None = None) -> str:
    """Render the summary; returns the captured plain-text output for tests."""
    capture_buf = io.StringIO()
    console = console or Console(file=capture_buf, width=100, force_terminal=False)

    if summary.total_sessions == 0:
        console.print(
            "[bold]No session reports yet.[/bold]\n"
            "Run [cyan]speakloop practice[/cyan] to create your first one."
        )
        return capture_buf.getvalue()

    # 1. Totals + date range.
    earliest, latest = summary.date_range
    console.print(
        f"[bold]Total sessions:[/bold] {summary.total_sessions}    "
        f"[bold]Date range:[/bold] {earliest} → {latest}"
    )

    # 2. Per-metric attempt-3 trajectory (compact).
    if any(summary.metric_series.values()):
        metric_table = Table(title="Fluency metrics (attempt 3)", show_lines=False)
        metric_table.add_column("Metric")
        metric_table.add_column("First")
        metric_table.add_column("Latest")
        metric_table.add_column("Δ", justify="right")
        for name, series in summary.metric_series.items():
            if not series:
                continue
            first = series[0][1]
            latest_val = series[-1][1]
            delta = latest_val - first
            label = METRIC_LABELS.get(name, name)
            metric_table.add_row(label, f"{first:.1f}", f"{latest_val:.1f}", _delta_cell(name, delta))
        console.print(metric_table)

    # 3. Top-N grammar pattern ranking.
    if summary.pattern_ranking:
        rank_table = Table(title=f"Top {len(summary.pattern_ranking)} grammar patterns")
        rank_table.add_column("Rank")
        rank_table.add_column("Pattern")
        rank_table.add_column("Occurrences", justify="right")
        rank_table.add_column("Sessions", justify="right")
        for i, row in enumerate(summary.pattern_ranking, start=1):
            rank_table.add_row(
                str(i),
                row.label,
                str(row.total_occurrences),
                str(len(row.session_ids)),
            )
        console.print(rank_table)
    else:
        console.print("No grammar patterns yet (Phase C reports gain them).")

    # 4. Per-pattern occurrence trend across sessions (010 P2a, FR-009 "stats").
    if summary.pattern_series:
        trend_table = Table(title="Per-pattern trend (recent sessions)")
        trend_table.add_column("Pattern")
        trend_table.add_column("Occurrences over time", justify="right")
        # order by the same ranking when available, else by label
        order = [row.label for row in summary.pattern_ranking] or sorted(summary.pattern_series)
        for label in order:
            series = summary.pattern_series.get(label)
            if series:
                trend_table.add_row(label, format_series(series, window=5))
        console.print(trend_table)

    return capture_buf.getvalue()
