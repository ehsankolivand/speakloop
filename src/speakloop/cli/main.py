"""`speakloop` top-level CLI entrypoint.

CRITICAL: must NOT import engine modules (kokoro_mlx, parakeet_mlx, mlx_lm)
or anything pulling them transitively at module-load time, so `speakloop
--help` and `speakloop --version` work without any model present
(FR-018, SC-006 — ≤ 2 s).
"""

from __future__ import annotations

from pathlib import Path

import typer

from speakloop import __version__
from speakloop.config import paths

app = typer.Typer(
    name="speakloop",
    help="Local English interview-practice CLI (TTS + ASR + LLM, offline).",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"speakloop {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Print version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    qa_file: Path = typer.Option(
        None, "--qa-file", help="Path to the Q&A YAML file (default: ~/.speakloop/qa.yaml)."
    ),
    models_dir: Path = typer.Option(
        None, "--models-dir", help="Path to the models directory (default: ~/.speakloop/models)."
    ),
) -> None:
    """speakloop — local interview practice."""
    if qa_file is not None:
        paths.set_qa_file_path(qa_file)
    if models_dir is not None:
        paths.set_models_dir(models_dir)


@app.command("practice")
def practice_cmd(
    question: str = typer.Option(None, "--question", help="Skip picker; jump to this question id."),
    listen_only: bool = typer.Option(
        False, "--listen-only", help="Skip the attempt phase even when ASR is installed."
    ),
) -> None:
    """Run a practice session."""
    from speakloop.cli import practice as _practice  # local import; engine touch is deferred.

    _practice.run(question=question, listen_only=listen_only)


@app.command("doctor")
def doctor_cmd(
    as_json: bool = typer.Option(False, "--json", help="Emit results as JSON for scripting."),
) -> None:
    """Run the health-check; exits non-zero if any check fails."""
    from speakloop.cli import doctor as _doctor

    _doctor.run(as_json=as_json)


@app.command("trends")
def trends_cmd(
    sessions_dir: Path = typer.Option(
        None, "--sessions-dir", help="Override the report directory (default: data/sessions/)."
    ),
    top_patterns: int = typer.Option(
        10, "--top-patterns", help="How many grammar patterns to rank."
    ),
    since: str = typer.Option(
        None, "--since", help="Filter to reports started on or after YYYY-MM-DD."
    ),
) -> None:
    """Render an aggregated summary across past session reports."""
    from speakloop.cli import trends as _trends

    _trends.run(sessions_dir=sessions_dir, top_patterns=top_patterns, since=since)


if __name__ == "__main__":
    app()
