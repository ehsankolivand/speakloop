"""`speakloop today` — the due queue (010-interview-loop, P2b, FR-012).

Read-only over the question bank + the derived store; loads NO engines
(Principle VIII). Rebuilds the store from session files if it is missing.
"""

from __future__ import annotations

from datetime import date as _date

import typer
from rich.console import Console
from rich.table import Table

from speakloop.config import loop_config, paths
from speakloop.content import QALoadError, load


def run(*, limit: int | None = None, today: _date | None = None) -> None:
    console = Console()
    qa_path = paths.resolve_qa_file()
    if qa_path is None:
        console.print("[red]No question file found.[/red] Run `speakloop practice` for setup guidance.")
        raise typer.Exit(1)
    try:
        qa_file = load(qa_path)
    except QALoadError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    from speakloop.srs.queue import due_queue
    from speakloop.store import io as store_io
    from speakloop.store import rebuild as store_rebuild

    store_path = paths.store_path()
    store = store_io.load(store_path)
    if not store.schedule and not store.patterns:
        # Cold/missing store → rebuild from session files so `today` is meaningful.
        store = store_rebuild.rebuild(paths.sessions_dir())

    cfg = loop_config.load()
    capacity = limit if limit is not None else cfg.daily_capacity
    today = today or _date.today()
    all_ids = [q.id for q in qa_file.questions]
    queue = due_queue(store.schedule, all_ids, today=today, capacity=capacity)

    if not queue.items:
        console.print(
            "[green]Nothing due — every question is at mastery.[/green] "
            "Run [cyan]speakloop practice[/cyan] for free practice anyway."
        )
        return

    table = Table(title=f"Due today ({today.isoformat()})")
    table.add_column("#", justify="right")
    table.add_column("Question")
    table.add_column("Last grade")
    table.add_column("Status")
    for i, item in enumerate(queue.items, start=1):
        if item.is_new:
            status = "new"
        elif item.days_overdue > 0:
            status = f"{item.days_overdue}d overdue"
        else:
            status = "due"
        table.add_row(str(i), item.question_id, item.last_grade or "—", status)
    console.print(table)
    if queue.carried_forward:
        console.print(f"[dim]+{queue.carried_forward} more carried forward to a later day.[/dim]")
    console.print("\nRun [cyan]speakloop practice[/cyan] to work through them.")
