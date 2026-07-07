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
        None,
        "--qa-file",
        help=(
            "Path to a Q&A YAML file. Precedence: this flag, then the personal "
            "override ~/.speakloop/qa.yaml (if present), then the in-repo default "
            "content/questions.yaml."
        ),
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
    no_audio: bool = typer.Option(
        False, "--no-audio", help="Skip reading the debrief feedback aloud; show it visually only."
    ),
    asr_engine: str = typer.Option(
        None,
        "--asr-engine",
        help="ASR engine: 'whisper' (default) or 'parakeet'. Whisper falls back to Parakeet on load failure.",
    ),
    cloud: bool = typer.Option(
        False,
        "--cloud",
        help="Alias for --engine openrouter (use the OpenRouter cloud model for feedback).",
    ),
    engine: str = typer.Option(
        None,
        "--engine",
        help=(
            "Analysis engine: 'local' (offline Qwen), 'openrouter' (cloud), or 'claude' (your "
            "local Claude Code, subscription-billed). Overrides the persisted default for this "
            "run only; set the default once with `speakloop setup`. --cloud == --engine openrouter."
        ),
    ),
    speed: float = typer.Option(
        0.85,
        "--speed",
        help=(
            "TTS playback speed multiplier (1.0 = normal). Lower is slower — good "
            "for shadowing. Default 0.85; try 0.7 for very slow."
        ),
    ),
    timings: bool = typer.Option(
        False,
        "--timings",
        help="Print a per-stage timing breakdown at the end of the session.",
    ),
    drills: bool = typer.Option(
        None,
        "--drills/--no-drills",
        help=(
            "Override the persisted pronunciation-drill setting for this run: --drills offers "
            "read-aloud drills during the feedback wait, --no-drills skips them. The safety gate "
            "(engine + free memory) still applies. Default: the loop.yaml `pronunciation_drills` "
            "setting (auto)."
        ),
    ),
) -> None:
    """Run a practice session."""
    from speakloop.cli import practice as _practice  # local import; engine touch is deferred.

    _practice.run(
        question=question,
        listen_only=listen_only,
        no_audio=no_audio,
        asr_engine_choice=asr_engine,
        cloud=cloud,
        engine=engine,
        speed=speed,
        timings=timings,
        drills=drills,
    )


@app.command("pronounce")
def pronounce_cmd(
    limit: int = typer.Option(
        None,
        "--limit",
        help=(
            "Max number of base sentences per round (default 6). The standalone trainer is "
            "user-paced — press q to stop, or answer the 'practise another round?' prompt."
        ),
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help=(
            "Show + log the real reason a drill 'could not score' (microphone vs scoring-model "
            "failure) instead of the vague message. Writes a log under the data dir."
        ),
    ),
) -> None:
    """Practise pronunciation standalone: hear → say → see → retry, outside an interview."""
    from speakloop.cli import pronounce as _pronounce  # local import; engine touch is deferred.

    _pronounce.run(limit=limit, debug=debug)


@app.command("setup")
def setup_cmd(
    engine: str = typer.Option(
        None,
        "--engine",
        help=(
            "Feedback engine to set as the default: 'local' (offline Qwen), 'openrouter' "
            "(cloud), or 'claude' (local Claude Code). Omit to choose interactively."
        ),
    ),
    no_download: bool = typer.Option(
        False,
        "--no-download",
        help="Persist the engine choice without downloading any models in this run.",
    ),
) -> None:
    """Choose and persist your feedback engine, and download only what that engine needs."""
    from speakloop.cli import setup as _setup

    _setup.run(engine=engine, no_download=no_download)


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


@app.command("today")
def today_cmd(
    limit: int = typer.Option(
        None, "--limit", help="Max questions to show (default: the loop config's daily capacity)."
    ),
) -> None:
    """Show the due queue — what to practice today, in priority order."""
    from speakloop.cli import today as _today

    _today.run(limit=limit)


@app.command("rebuild")
def rebuild_cmd(
    sessions_dir: Path = typer.Option(
        None, "--sessions-dir", help="Override the report directory (default: data/sessions/)."
    ),
) -> None:
    """Rebuild the derived store (SRS schedule + key-point cache + pattern series) from session files."""
    from speakloop.cli import rebuild as _rebuild

    _rebuild.run(sessions_dir=sessions_dir)


@app.command("resume")
def resume_cmd(
    cloud: bool = typer.Option(
        False, "--cloud", help="Alias for --engine openrouter (re-run analysis via OpenRouter)."
    ),
    engine: str = typer.Option(
        None,
        "--engine",
        help=(
            "Analysis engine for the re-run: 'local' (default), 'openrouter', or 'claude'. "
            "Overrides the loop-config `engine:` default. --cloud is an alias for "
            "--engine openrouter."
        ),
    ),
    timings: bool = typer.Option(
        False,
        "--timings",
        help="Print a per-stage timing breakdown for the re-run analysis.",
    ),
) -> None:
    """Finish any session left analysis-pending (re-runs analysis over the saved transcripts)."""
    from speakloop.cli import resume as _resume

    _resume.run(cloud=cloud, engine=engine, timings=timings)


questions_app = typer.Typer(
    name="questions",
    help="Author, validate, and locate your question file.",
    no_args_is_help=True,
    add_completion=False,
)


@questions_app.command("validate")
def questions_validate_cmd(
    path: Path = typer.Argument(
        None, help="Question file to validate (default: the resolved active file)."
    ),
) -> None:
    """Validate a question file and report precise, per-entry errors."""
    from speakloop.cli import questions as _questions

    _questions.validate(path)


@questions_app.command("template")
def questions_template_cmd() -> None:
    """Print a commented starter question file to stdout (redirect it to save)."""
    from speakloop.cli import questions as _questions

    _questions.template()


@questions_app.command("where")
def questions_where_cmd() -> None:
    """Show the question-file precedence and the currently-active file."""
    from speakloop.cli import questions as _questions

    _questions.where()


app.add_typer(questions_app)


if __name__ == "__main__":
    app()
