"""`speakloop shadow` — the answer-shadowing trainer (018, US2).

Splits a chosen question's ideal answer into sentences; for each, the local TTS speaks it, the
learner repeats it, the resident ASR transcribes the repeat, and the app gives deterministic
OFFLINE feedback: content-word completeness (which key words were covered / missed, warm-up-judge
style) plus pace and fillers from `metrics.compute_all`. Provisions TTS + ASR (Phase B) only —
NOT the phoneme scorer, no LLM. No report is written; the recording is deleted after transcription.

All heavy imports are function-local so `speakloop --help` never loads a model; `main.py` imports
this module only inside the command body. See `specs/018-self-practice-modes/contracts/shadow-command.md`.
"""

from __future__ import annotations

import contextlib
import threading
import time
from pathlib import Path

import typer
from rich.console import Console

from speakloop.cli.gate_prompt import is_interactive as _is_interactive


def _provision(console: Console, *, input_fn) -> bool:
    """Ensure TTS + ASR (Phase B) are present via the existing consent/download flow. NOT the
    pronunciation phoneme scorer. Returns True to proceed, False on decline/failure."""
    from speakloop import installer

    try:
        installer.ensure_models("B", console=console, input_fn=input_fn)
    except installer.InstallDeclinedError:
        console.print(
            "[yellow]Models declined — nothing to shadow. Run `speakloop shadow` again when "
            "you're ready to download the speech models.[/yellow]"
        )
        return False
    except installer.InstallFailedError as e:
        console.print(f"[yellow]Speech models unavailable ({e}); cannot run shadowing.[/yellow]")
        return False
    return True


def _pick_question(questions, question_id, console: Console, *, input_fn):
    """Resolve the question to shadow by ``--question`` id or an interactive picker."""
    if question_id:
        for q in questions:
            if q.id == question_id:
                return q
        console.print(f"[red]No question with id '{question_id}'.[/red]")
        raise typer.Exit(1)
    console.print("[bold]Pick a question to shadow:[/bold]")
    for i, q in enumerate(questions, start=1):
        console.print(f"  [cyan]{i}[/cyan]. {q.id}")
    while True:
        try:
            raw = input_fn("Number (Enter or q to cancel): ").strip().lower()
        except EOFError:
            return None
        if raw in {"", "q", "quit"}:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(questions):
            return questions[int(raw) - 1]
        console.print("[yellow]Enter a valid number.[/yellow]")


def _show_feedback(console: Console, sentence: str, transcript) -> None:
    """Deterministic, offline per-sentence feedback: completeness + pace + fillers."""
    from speakloop import metrics, shadowing

    result = shadowing.judge_completeness(sentence, transcript.text)
    if not result.captured:
        console.print("  [yellow]Didn't catch a repeat — that one won't count. Keep going.[/yellow]")
        return
    if result.content_words:
        tag = "[green]strong[/green]" if result.is_strong else "[yellow]keep at it[/yellow]"
        console.print(
            f"  Completeness: {len(result.covered)}/{len(result.content_words)} key words — {tag}."
        )
        if result.missed:
            console.print(f"  [dim]Missed:[/dim] {', '.join(result.missed)}")
    else:
        console.print("  [dim](no key content words to check in this sentence)[/dim]")
    m = metrics.compute_all(transcript)
    console.print(
        f"  [dim]Pace:[/dim] {float(m['speech_rate_wpm']):.0f} wpm · "
        f"[dim]fillers:[/dim] {int(m['filler_words_count'])}"
    )


def run(
    *,
    question_id: str | None = None,
    limit: int | None = None,
    slow: bool = False,
    tts_engine=None,
    play_fn=None,
    record_fn=None,
    transcribe_fn=None,
    key_reader=None,
    qa_file: Path | None = None,
    scratch_dir: Path | None = None,
    input_fn=input,
    console: Console | None = None,
) -> None:
    """Entry point for `speakloop shadow`. Everything model/mic/tty is injectable for tests."""
    console = console or Console()
    from speakloop import content, shadowing
    from speakloop.config import loop_config, paths

    qa_path = Path(qa_file) if qa_file is not None else paths.resolve_qa_file()
    if qa_path is None or not Path(qa_path).exists():
        console.print(
            "[yellow]No question file found. Add content/questions.yaml or pass --qa-file.[/yellow]"
        )
        raise typer.Exit(1)
    try:
        qa = content.load(Path(qa_path))
    except Exception as e:  # noqa: BLE001 — surface a clean message, not a traceback
        console.print(f"[red]Could not load questions: {e}[/red]")
        raise typer.Exit(1) from e
    if not qa.questions:
        console.print("[yellow]No questions to shadow.[/yellow]")
        raise typer.Exit(1)

    question = _pick_question(qa.questions, question_id, console, input_fn=input_fn)
    if question is None:
        console.print("Bye.")
        return

    sentences = shadowing.split_sentences(question.ideal_answer)
    if limit and limit > 0:
        sentences = sentences[:limit]
    if not sentences:
        console.print("[yellow]That answer has no sentences to shadow.[/yellow]")
        return

    if not _is_interactive():
        console.print(
            "[yellow]Shadowing records your voice and needs an interactive terminal; skipping.[/yellow]"
        )
        return

    # Build the real engines only when we must (tests inject fakes → skip download).
    need_build = (
        tts_engine is None or play_fn is None or record_fn is None or transcribe_fn is None
    )
    if need_build and not _provision(console, input_fn=input_fn):
        return

    cfg = loop_config.load()
    if tts_engine is None:
        from speakloop.tts.kokoro_engine import KokoroEngine

        tts_engine = KokoroEngine(speed=cfg.pronunciation_tts_speed)
    if play_fn is None:
        from speakloop.audio import playback

        play_fn = playback.play
    if record_fn is None:
        from speakloop.audio import recorder

        record_fn = recorder.record
    if transcribe_fn is None:
        from speakloop import asr

        _asr_engine = asr.build_engine().engine
        transcribe_fn = _asr_engine.transcribe
    if key_reader is None:
        from speakloop.sessions import keyboard

        key_reader = keyboard.make_key_reader()

    from speakloop.sessions.coordinator import DRILL_BUDGET_SECONDS, _record_stage

    scratch_dir = Path(scratch_dir) if scratch_dir is not None else (paths.sessions_dir().parent / ".tmp-shadow")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    teach_speed = loop_config.teach_speed(cfg.pronunciation_tts_speed)
    early_exit = threading.Event()

    def speak(text: str, *, slower: bool) -> None:
        if slower:
            try:
                wav = tts_engine.synthesize(text, speed=teach_speed)
            except TypeError:
                wav = tts_engine.synthesize(text)
        else:
            wav = tts_engine.synthesize(text)
        play_fn(wav)

    console.print(
        f"\n[bold]Answer shadowing[/bold] — {question.id}, {len(sentences)} sentence(s). "
        "Hear each one, then repeat it. Press [bold]q[/bold] to stop.\n"
    )

    completed = 0
    for idx, sentence in enumerate(sentences, start=1):
        console.print(f"\n[bold cyan]Sentence {idx}/{len(sentences)}[/bold cyan]")
        console.print(f"  [dim]{sentence}[/dim]")
        speak(sentence, slower=slow)
        # let the learner replay (slower) or quit before recording
        action = "record"
        while True:
            try:
                resp = input_fn("[Enter] repeat it · [r] replay slower · [q] quit: ").strip().lower()
            except EOFError:
                resp = "q"
            if resp in {"q", "quit"}:
                action = "quit"
                break
            if resp in {"r", "replay"}:
                speak(sentence, slower=True)
                continue
            break
        if action == "quit":
            break

        wav_path = scratch_dir / f"shadow-{idx}.wav"
        early_exit.clear()
        try:
            _record_stage(
                record_fn=record_fn, wav_path=wav_path, budget=DRILL_BUDGET_SECONDS,
                label="Repeat it", key_reader=key_reader, ui_sleep=time.sleep,
                console=console, early_exit_event=early_exit,
            )
            transcript = transcribe_fn(wav_path)
        finally:
            with contextlib.suppress(OSError):
                wav_path.unlink()
        _show_feedback(console, sentence, transcript)
        completed += 1

    console.print(
        f"\n[bold]Shadowing complete[/bold] — {completed} sentence(s). "
        "Nice work; come back any time with `speakloop shadow`."
    )
