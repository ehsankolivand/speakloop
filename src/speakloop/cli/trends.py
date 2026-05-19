"""`speakloop trends` — cross-session dashboard (Phase C)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from rich.console import Console

from speakloop.config import paths
from speakloop.trends import aggregator, reader, renderer


def run(
    *,
    sessions_dir: Path | None = None,
    top_patterns: int = 10,
    since: str | None = None,
) -> None:
    console = Console()
    sd = Path(sessions_dir) if sessions_dir is not None else paths.sessions_dir()

    since_date: date | None = None
    if since:
        try:
            since_date = date.fromisoformat(since)
        except ValueError:
            console.print(f"[red]Invalid --since value {since!r}; expected YYYY-MM-DD.[/red]")
            raise SystemExit(1)

    result = reader.read_reports(sd, since=since_date)
    for path, reason in result.skipped:
        console.print(f"[yellow]Skipping malformed report:[/yellow] {path} — {reason}")

    summary = aggregator.aggregate(result.reports, top_n=top_patterns)
    print(renderer.render(summary, console=console))
