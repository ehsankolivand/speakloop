"""`speakloop practice` — listen loop in Phase A, full 4/3/2 loop in Phase B/C."""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

import typer
from rich.console import Console

from speakloop import installer
from speakloop.audio import devices, playback
from speakloop.config import paths
from speakloop.content import QALoadError, load


def _ensure_starter_qa(console: Console) -> Path:
    """Copy the starter Q&A file to the user qa_file_path on first run."""
    target = paths.qa_file_path()
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    starter_text = (
        resources.files("speakloop.content").joinpath("starter.yaml").read_text(encoding="utf-8")
    )
    target.write_text(starter_text, encoding="utf-8")
    console.print(f"Created starter Q&A at [bold]{target}[/bold]. Edit it any time.")
    return target


def _pick_question(qa_file, console: Console) -> speakloop.content.Question | None:  # noqa: F821
    """Render a numbered picker and return the chosen Question (or None on cancel)."""
    console.print()
    console.print("[bold]Available questions:[/bold]")
    for i, q in enumerate(qa_file.questions, start=1):
        first_line = q.question.strip().splitlines()[0]
        if len(first_line) > 80:
            first_line = first_line[:77] + "…"
        console.print(f"  [cyan]{i}[/cyan]. {q.id} — {first_line}")
    console.print()
    raw = input("Pick a question by number (or q to quit): ").strip().lower()
    if raw in {"", "q", "quit"}:
        return None
    if not raw.isdigit():
        console.print("[red]Invalid input.[/red]")
        return None
    idx = int(raw) - 1
    if idx < 0 or idx >= len(qa_file.questions):
        console.print("[red]Out of range.[/red]")
        return None
    return qa_file.questions[idx]


def _read_key() -> str:
    """Return a canonical command key: 'r', 'R', 'q', ' ' (space=next), or '' (Enter/EOF).

    Two-tier strategy (the prior readchar path was observed to fall through
    under some macOS terminal/`uv run` combos):

      Tier 1 — raw single-byte read: try fd 0 first; if that isn't a tty,
        try opening /dev/tty (handles cases where stdin was redirected but
        the controlling terminal is still reachable). Uses termios+cbreak +
        os.read(fd, 1) so we don't depend on Python-level line buffering.

      Tier 2 — line-buffered input(): accepts the same commands as full
        words for scripted/piped use ('r', 'R', 'space', 'q', 'quit', 'next').
        Case is preserved so 'r' (lowercase replay question) and 'R' (replay
        ideal answer) remain distinct.
    """
    # Tier 1a: stdin.
    fd: int | None = None
    try:
        fd = sys.stdin.fileno()
    except (OSError, ValueError):
        fd = None
    if fd is not None and os.isatty(fd):
        ch = _cbreak_read(fd)
        if ch is not None:
            return ch

    # Tier 1b: controlling terminal even if stdin was redirected.
    tty_fd: int | None = None
    try:
        tty_fd = os.open("/dev/tty", os.O_RDONLY)
    except OSError:
        tty_fd = None
    if tty_fd is not None:
        try:
            ch = _cbreak_read(tty_fd)
        finally:
            try:
                os.close(tty_fd)
            except OSError:
                pass
        if ch is not None:
            return ch

    # Tier 2: line-buffered fallback (tests, piped input, last resort).
    try:
        line = input()
    except EOFError:
        return ""
    return _parse_line_command(line)


def _cbreak_read(fd: int) -> str | None:
    """Put `fd` into cbreak, read one byte, restore. Return canonical key or None on failure."""
    import termios
    import tty

    try:
        saved = termios.tcgetattr(fd)
    except termios.error:
        return None
    try:
        tty.setcbreak(fd, termios.TCSANOW)
        try:
            data = os.read(fd, 1)
        except OSError:
            return None
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        except termios.error:
            pass
    if not data:
        return ""  # EOF on the tty — treat as "next"
    try:
        ch = data.decode("utf-8")
    except UnicodeDecodeError:
        return ""
    if ch in ("\r", "\n"):
        return ""
    if ch == "\x03":  # Ctrl-C
        return "q"
    return ch[:1]


def _parse_line_command(line: str) -> str:
    """Map a typed line to a canonical key.

    `input()` has already stripped the trailing newline, so:
      ""              → "" (Enter alone, or EOFError upstream)
      " " / "   "     → " " (whitespace-only line is the line-buffered
                            analogue of pressing the space bar)
      "r"             → "r"   (case-sensitive)
      "R"             → "R"   (case-sensitive)
      "q" / "quit"    → "q"   (case-insensitive)
      "space"         → " "   (case-insensitive)
      anything else   → first char, so caller can surface an [Unknown key] message
    """
    if not line:
        return ""
    if not line.strip():
        return " "
    stripped = line.strip()
    if stripped == "r":
        return "r"
    if stripped == "R":
        return "R"
    lower = stripped.lower()
    if lower in {"q", "quit"}:
        return "q"
    if lower == "space":
        return " "
    return stripped[:1]


def _listen_loop(question, console: Console, tts_engine, play_fn) -> str:
    """Play question + ideal answer; loop on replay commands.

    Returns the canonical exit key so the caller can route Phase B:
      ' '  → space pressed → advance to attempts
      'q'  → q pressed → quit
      ''   → Enter / EOF / Ctrl-D → quit (safer default than auto-advancing)
    'r' and 'R' stay inside the loop and trigger replay.
    """

    def _play(label: str, wav: Path) -> None:
        console.print(f"[dim]▶ playing {label}…[/dim]")
        play_fn(wav)
        console.print("[dim]done[/dim]")

    voice = question.voice_override
    q_wav = tts_engine.synthesize(question.question, voice=voice)
    a_wav = tts_engine.synthesize(question.ideal_answer, voice=voice)

    console.print(f"\n[bold]Question:[/bold] {question.id}\n")
    console.print(question.question.strip())
    _play("question", q_wav)
    console.print("\n[bold]Ideal answer:[/bold]\n")
    console.print(question.ideal_answer.strip())
    _play("ideal answer", a_wav)

    while True:
        console.print(
            "\n[dim](r) replay question  (R) replay ideal answer  (space) next  (q) quit[/dim]"
        )
        # Flush so the prompt appears before we block on the keypress.
        sys.stdout.flush()
        key = _read_key()
        if key == "r":
            _play("question", q_wav)
        elif key == "R":
            _play("ideal answer", a_wav)
        elif key == " ":
            return " "
        elif key in ("q", "Q"):
            return "q"
        elif key == "":
            return ""
        else:
            console.print(f"[red]Unknown key: {key!r}[/red]")


def run(
    *,
    question: str | None = None,
    listen_only: bool = False,
    tts_engine=None,
    play_fn=None,
    audio_devices=devices,
) -> None:
    """Entry point for `speakloop practice`."""
    console = Console()

    qa_path = _ensure_starter_qa(console)
    try:
        qa_file = load(qa_path)
    except QALoadError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    # Resolve the question.
    chosen = None
    if question:
        chosen = next((q for q in qa_file.questions if q.id == question), None)
        if chosen is None:
            console.print(f"[red]No question with id {question!r}.[/red]")
            raise typer.Exit(1)
    else:
        chosen = _pick_question(qa_file, console)
        if chosen is None:
            console.print("Bye.")
            return

    # Pick the model phase from the user's intent. --listen-only only needs
    # Phase A (TTS); without it we need Phase B (TTS + ASR) to record attempts.
    # Phase C (LLM) is opted into separately when the model is present.
    target_phase = "A" if listen_only else "B"

    try:
        installer.ensure_models(target_phase, console=console)
    except installer.InstallDeclinedError:
        console.print("[yellow]Model download declined; nothing to do.[/yellow]")
        raise typer.Exit(1)
    except installer.InstallFailedError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if tts_engine is None:
        from speakloop.tts.kokoro_engine import KokoroEngine

        tts_engine = KokoroEngine()
    if play_fn is None:
        play_fn = playback.play

    # Listen phase runs in both modes — the user hears the question + ideal
    # answer before deciding to advance to attempts.
    exit_key = _listen_loop(chosen, console, tts_engine, play_fn)

    if listen_only or exit_key != " ":
        # listen-only flag, or user pressed q / Enter — done.
        return

    # Phase B: advance to attempts. Pre-check microphone (FR-009).
    if audio_devices.default_input() is None:
        console.print("[red]No microphone detected. Run `speakloop doctor` for remediation.[/red]")
        raise typer.Exit(1)

    from speakloop.sessions.coordinator import run_session

    grammar_analyzer = _build_grammar_analyzer()

    run_session(
        chosen,
        tts_engine=tts_engine,
        play_fn=play_fn,
        console=console,
        grammar_analyzer=grammar_analyzer,
    )


def _build_grammar_analyzer():
    """Return a callable `(transcripts) -> patterns` if Phase C LLM is installed; else None."""
    from speakloop.installer import manifest, validator

    if not validator.validate(manifest.QWEN3_8B_4BIT).ok:
        return None

    from speakloop.feedback.grammar_analyzer import analyze
    from speakloop.llm.qwen_engine import QwenEngine

    qwen = QwenEngine()

    def _runner(transcripts):
        return analyze(transcripts, qwen)

    return _runner
