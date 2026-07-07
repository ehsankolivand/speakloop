"""Rich-rendered consent prompt with size disclosure. Decline-by-default (FR-019, FR-020)."""

from __future__ import annotations

import sys
from collections.abc import Iterable

from rich.console import Console
from rich.table import Table

from speakloop.installer.manifest import Model


def _human_size(n: int) -> str:
    # DECIMAL units (1000-based) to MATCH the labels: rich's `DownloadColumn` shows decimal GB
    # during the transfer and macOS reports free space in decimal GB, so an 8e9-byte model must
    # read "8.0 GB" — not the "7.5 GB" a binary divisor under a GB label produced (IMP-041).
    for unit, divisor in [("GB", 10**9), ("MB", 10**6), ("KB", 10**3)]:
        if n >= divisor:
            return f"{n / divisor:.1f} {unit}"
    return f"{n} B"


def prompt_for_consent(
    models: Iterable[Model],
    *,
    console: Console | None = None,
    input_fn=input,
) -> bool:
    """Show the model list + total disk footprint and ask Y/N. Default N."""
    console = console or Console(file=sys.stderr)
    models_list = list(models)

    table = Table(title="Models required for this phase", show_lines=False)
    table.add_column("Model")
    table.add_column("HF repo")
    table.add_column("Size", justify="right")
    table.add_column("Target path")

    total = 0
    for m in models_list:
        table.add_row(m.name, m.hf_repo_id, _human_size(m.expected_size_bytes), str(m.local_path))
        total += m.expected_size_bytes

    console.print(table)
    console.print(f"[bold]Total disk footprint:[/bold] {_human_size(total)}")
    console.print("All artifacts stay on your local machine. No telemetry.")

    try:
        answer = input_fn("Proceed with download? [y/N]: ")
    except EOFError:
        return False

    return answer.strip().lower() in {"y", "yes"}
