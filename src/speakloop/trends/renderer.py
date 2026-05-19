"""Render a TrendsSummary to the terminal via rich."""

from __future__ import annotations

import io

from rich.console import Console
from rich.table import Table

from speakloop.trends.aggregator import TrendsSummary


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
            metric_table.add_row(name, f"{first:.1f}", f"{latest_val:.1f}", f"{delta:+.1f}")
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

    return capture_buf.getvalue()
