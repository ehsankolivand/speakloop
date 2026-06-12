"""`speakloop questions` — author, validate, and locate your question file (015).

Thin command layer over the existing loader/schema (`content.load` already yields file:line
on YAML errors and entry-id + field on schema errors) plus the canonical
`content.template`. `template` prints to stdout only — nothing is auto-created in the home
directory, preserving the question-file precedence and no-auto-create guarantees.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from speakloop.config import paths
from speakloop.content import QALoadError, load
from speakloop.content.template import template_text


def validate(path: Path | None = None, *, console: Console | None = None) -> None:
    """Validate a question file (an explicit path, or the resolved active file)."""
    console = console or Console()
    target = path if path is not None else paths.resolve_qa_file()
    if target is None:
        console.print(
            "[red]No question file found.[/red] Looked for the personal override "
            f"[bold]{paths.qa_file_path()}[/bold] and the in-repo default "
            f"[bold]{paths.default_qa_file()}[/bold].\n"
            "Pass a path (`speakloop questions validate <file>`) or create one with "
            "`speakloop questions template`."
        )
        raise typer.Exit(1)
    try:
        qa = load(target)
    except QALoadError as e:
        console.print(f"[red]Invalid question file:[/red] {escape(str(e))}")
        raise typer.Exit(1) from e
    console.print(f"[green]OK[/green] — {target}: {len(qa.questions)} question(s).")
    for warning in qa.warnings:
        console.print(f"  [yellow]warning:[/yellow] {escape(warning)}")


def template(*, console: Console | None = None) -> None:
    """Print the canonical commented template to stdout (plain print — no markup parsing)."""
    print(template_text(), end="")


def where(*, console: Console | None = None) -> None:
    """Show the question-file precedence and the currently-active file."""
    console = console or Console()
    console.print("[bold]Question-file precedence[/bold] (first match wins):")
    console.print("  1. --qa-file PATH or SPEAKLOOP_QA_FILE (explicit override)")
    console.print(f"  2. personal override: {paths.qa_file_path()}")
    console.print(f"  3. in-repo default:   {paths.default_qa_file()}")
    active = paths.resolve_qa_file()
    if active is None:
        console.print(
            "\n[yellow]Active file:[/yellow] none found — create one with "
            "`speakloop questions template > <path>`."
        )
        return
    try:
        qa = load(active)
        suffix = f" ({len(qa.questions)} question(s))"
    except QALoadError:
        suffix = " [red](present but invalid — run `questions validate`)[/red]"
    console.print(f"\n[green]Active file:[/green] {active}{suffix}")
