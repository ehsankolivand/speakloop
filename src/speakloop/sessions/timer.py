"""Per-attempt countdown timer using rich.progress."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)

# Per FR-005..FR-007: 4 min / 3 min / 2 min budgets.
BUDGETS = (240, 180, 120)


def time_budget_for(ordinal: int) -> int:
    if ordinal < 1 or ordinal > 3:
        raise ValueError(f"ordinal must be 1..3, got {ordinal}")
    return BUDGETS[ordinal - 1]


def run(
    budget_seconds: int,
    *,
    early_exit_event: threading.Event | None = None,
    on_tick: Callable[[float], None] | None = None,
    console: Console | None = None,
) -> float:
    """Block for up to `budget_seconds` while rendering a countdown.

    Returns the actual elapsed seconds.
    `early_exit_event.set()` interrupts before zero.
    """
    early_exit_event = early_exit_event or threading.Event()

    progress = Progress(
        TextColumn("[bold]Recording[/bold]"),
        BarColumn(),
        TextColumn("{task.completed:.0f}s / {task.total:.0f}s"),
        TimeRemainingColumn(),
        transient=True,
        console=console,
    )

    start = time.monotonic()
    with progress:
        task = progress.add_task("attempt", total=budget_seconds)
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= budget_seconds:
                break
            if early_exit_event.is_set():
                break
            progress.update(task, completed=elapsed)
            if on_tick is not None:
                on_tick(elapsed)
            time.sleep(0.1)

    return time.monotonic() - start
