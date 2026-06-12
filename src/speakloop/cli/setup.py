"""`speakloop setup` — pick + persist the feedback engine and download only what it needs (015).

Onboarding entry point: resolve the engine (explicit flag, or an interactive numbered
prompt, or keep the current persisted value when non-interactive), persist it to
`loop.yaml engine:` (the only writer of that file — Constitution / config CLAUDE.md), then
provision exactly that engine's models — TTS + ASR always; the large local feedback LLM
only for the `local` engine, never for a cloud engine. Finishes with an engine-aware
readiness summary. Engine imports stay function-local (via `installer`/`engine_status`) so
the CLI import remains model-free.
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console

from speakloop import installer
from speakloop.cli import engine_status
from speakloop.config import loop_config

_ENGINE_LABELS = {
    "local": "local — offline Qwen model (downloads the large local feedback LLM)",
    "openrouter": "openrouter — cloud feedback via OpenRouter (no large local LLM)",
    "claude": "claude — your local Claude Code CLI, subscription-billed (no large local LLM)",
}


def _resolve_engine(engine: str | None, console: Console, input_fn) -> str:
    """Resolve the engine to persist: explicit flag → interactive prompt → keep current."""
    from speakloop.config.loop_config import VALID_ENGINES

    if engine is not None:
        chosen = engine.strip().lower()
        if chosen not in VALID_ENGINES:
            console.print(
                f"[red]--engine must be one of {', '.join(VALID_ENGINES)} (got {engine!r}).[/red]"
            )
            raise typer.Exit(2)
        return chosen

    current = loop_config.load().engine
    # Non-interactive (piped/CI): keep the current persisted engine without prompting so
    # the command never hangs waiting on input.
    if not sys.stdin.isatty():
        console.print(
            f"[dim]No --engine given and input is not a terminal; keeping the current "
            f"engine ({current}).[/dim]"
        )
        return current

    console.print("[bold]Choose your feedback engine:[/bold]")
    options = list(VALID_ENGINES)
    for i, name in enumerate(options, start=1):
        marker = "  [green](current)[/green]" if name == current else ""
        console.print(f"  [cyan]{i}[/cyan]. {_ENGINE_LABELS[name]}{marker}")
    while True:
        raw = input_fn(f"Engine [1-{len(options)}, Enter keeps {current}]: ").strip().lower()
        if raw == "":
            return current
        if raw in options:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        console.print("[red]Invalid choice — pick a number or an engine name.[/red]")


def run(*, engine: str | None = None, no_download: bool = False, input_fn=input, console=None) -> None:
    """Entry point for `speakloop setup`."""
    console = console or Console()
    chosen = _resolve_engine(engine, console, input_fn)

    try:
        path = loop_config.save_engine(chosen)
    except ValueError as e:
        # A pre-existing loop.yaml that doesn't parse as a mapping — don't clobber it.
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None
    console.print(
        f"[green]Default feedback engine set to[/green] [bold]{chosen}[/bold] "
        f"[dim]({path})[/dim]. Override per run with --engine/--cloud."
    )

    if no_download:
        console.print(
            "[dim]--no-download: skipping model provisioning. "
            "Run `speakloop practice` later to download what's needed.[/dim]"
        )
    else:
        _provision(chosen, console)

    _report_readiness(chosen, console)
    console.print("\n[bold]Ready.[/bold] Run [cyan]speakloop practice[/cyan] to start a session.")


def _provision(engine: str, console: Console) -> None:
    """Download exactly what the chosen engine needs (size disclosure + consent reused).

    TTS + ASR (Phase B) are always required. The large local feedback model (Phase C) is
    fetched ONLY for the local engine; declining it degrades to no-grammar sessions rather
    than blocking. Cloud engines never reference the local feedback model (FR-006/FR-007).
    """
    try:
        installer.ensure_models("B", console=console)
    except installer.InstallDeclinedError:
        console.print(
            "[yellow]Speech/transcription download declined — practice can't record without "
            "them. Re-run `speakloop setup` when ready.[/yellow]"
        )
        raise typer.Exit(1) from None
    except installer.InstallFailedError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if installer.engine_needs_local_llm(engine, listen_only=False):
        try:
            installer.ensure_models("C", console=console)
        except installer.InstallDeclinedError:
            console.print(
                "[yellow]Local feedback model declined. Sessions will record but produce no "
                "grammar feedback until it's downloaded (re-run setup, or use a cloud "
                "engine).[/yellow]"
            )
        except installer.InstallFailedError as e:
            console.print(f"[yellow]Local feedback model unavailable ({e}).[/yellow]")


def _report_readiness(engine: str, console: Console) -> None:
    """Print the engine-aware readiness summary (active engine + each requirement + next step)."""
    readiness = engine_status.engine_readiness(engine)
    console.print(f"\n[bold]Active feedback engine:[/bold] {engine}")
    for req in readiness.requirements:
        if req.ok:
            icon = "[green]✓[/green]"
        elif req.optional:
            icon = "[yellow]○[/yellow]"
        else:
            icon = "[red]✗[/red]"
        console.print(f"  {icon} {req.label}: {req.detail}")
        if not req.ok and req.next_step:
            console.print(f"     [dim]→ {req.next_step}[/dim]")
