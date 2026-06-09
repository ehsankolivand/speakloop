"""Orchestrator for the 4/3/2 attempt loop.

State machine: `listening → attempt_1 → attempt_2 → attempt_3 → analyzing → reporting → done`.
A SIGINT at any state up to and including `reporting` aborts cleanly without writing a report.
"""

from __future__ import annotations

import os
import select
import shutil
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)

from speakloop.asr import ASREngine, Transcript, TranscriptionContext
from speakloop.audio import recorder
from speakloop.config import paths
from speakloop.content import Question
from speakloop.feedback import frontmatter, markdown_writer, narrative, report_builder
from speakloop.metrics import compute_all
from speakloop.sessions import abort, timer


class AbortedError(Exception):
    """Raised when the user aborts the session via SIGINT."""


class SessionResult(NamedTuple):
    """Return value of :func:`run_session` (data-model §D).

    Additive: the report is still written exactly as before (``report_path``),
    and the fully-populated in-memory ``session`` is returned alongside so the
    debrief can render from typed data without re-parsing the Markdown file.
    """

    report_path: Path
    session: frontmatter.Session


def _spawn_enter_reader(
    early_exit_event: threading.Event,
    stop_event: threading.Event,
) -> threading.Thread | None:
    """Background reader: set `early_exit_event` when the user presses Enter.

    Resolves a tty fd via the listen-loop's two-tier strategy: stdin if it's
    a tty, else `/dev/tty`. If neither is available (piped input, captured
    stdin under pytest, no controlling terminal), returns None so the
    coordinator simply runs without early-exit support.

    The reader polls `select.select` with a 100 ms timeout so it can notice
    `stop_event` after recording ends and exit promptly.
    """
    fd: int | None = None
    own_fd = False
    try:
        candidate = sys.stdin.fileno()
        if os.isatty(candidate):
            fd = candidate
    except (OSError, ValueError):
        fd = None
    if fd is None:
        try:
            fd = os.open("/dev/tty", os.O_RDONLY)
            own_fd = True
        except OSError:
            return None

    # Drain anything the user typed before recording started (e.g. stray
    # keystrokes after the listen-loop) so we don't spuriously trip
    # early-exit at t=0.
    try:
        import termios

        termios.tcflush(fd, termios.TCIFLUSH)
    except Exception:  # noqa: BLE001 — termios may be unavailable; best-effort drain
        pass

    def _reader() -> None:
        try:
            while not stop_event.is_set():
                try:
                    ready, _, _ = select.select([fd], [], [], 0.1)
                except (OSError, ValueError):
                    return
                if not ready:
                    continue
                try:
                    data = os.read(fd, 1024)
                except OSError:
                    return
                if not data:
                    return  # EOF
                # Canonical-mode reads only return after newline, so any
                # data here means the user hit Enter (with or without text).
                early_exit_event.set()
                return
        finally:
            if own_fd:
                try:
                    os.close(fd)
                except OSError:
                    pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return t


def _do_attempt(
    ordinal: int,
    *,
    record_fn,
    asr_engine: ASREngine,
    early_exit_event: threading.Event,
    console: Console,
    scratch_dir: Path,
    context: TranscriptionContext | None = None,
) -> tuple[float, Transcript]:
    budget = timer.time_budget_for(ordinal)
    console.print(
        f"\n[bold]Attempt {ordinal}[/bold] — budget {budget}s. "
        "[dim]🎙 speak now; press Enter to end early.[/dim]"
    )
    wav_path = scratch_dir / f"attempt-{ordinal}.wav"

    progress = Progress(
        TextColumn("[bold cyan]🎙[/bold cyan]"),
        BarColumn(),
        TextColumn("{task.completed:.0f}s / {task.total:.0f}s"),
        TimeRemainingColumn(),
        transient=True,
        console=console,
    )
    stop_helpers = threading.Event()
    ticker_thread: threading.Thread | None = None
    reader_thread: threading.Thread | None = None
    try:
        with progress:
            task_id = progress.add_task("attempt", total=budget)
            tick_start = time.monotonic()

            def _ticker() -> None:
                while not stop_helpers.is_set():
                    elapsed = time.monotonic() - tick_start
                    progress.update(task_id, completed=min(elapsed, float(budget)))
                    time.sleep(0.1)

            ticker_thread = threading.Thread(target=_ticker, daemon=True)
            ticker_thread.start()
            reader_thread = _spawn_enter_reader(early_exit_event, stop_helpers)

            duration = record_fn(
                wav_path,
                time_budget_seconds=budget,
                early_exit_event=early_exit_event,
            )
    finally:
        stop_helpers.set()
        if ticker_thread is not None:
            ticker_thread.join(timeout=1.0)
        if reader_thread is not None:
            reader_thread.join(timeout=1.0)

    if abort.abort_event.is_set():
        raise AbortedError()

    console.print(
        f"[green]✓ Attempt {ordinal}[/green] recorded — "
        f"{duration:.1f}s captured. [dim]Transcribing…[/dim]"
    )
    transcript = asr_engine.transcribe(wav_path, context=context)
    # Override the engine-reported duration with the wall-clock recording duration.
    transcript = Transcript(
        text=transcript.text,
        words=transcript.words,
        audio_duration_seconds=duration,
    )
    return duration, transcript


def _build_attempts(
    transcripts: list[Transcript],
) -> list[frontmatter.Attempt]:
    attempts: list[frontmatter.Attempt] = []
    for i, t in enumerate(transcripts, start=1):
        m = compute_all(t)
        attempts.append(
            frontmatter.Attempt(
                ordinal=i,
                time_budget_seconds=timer.time_budget_for(i),
                actual_duration_seconds=t.audio_duration_seconds,
                transcript=t.text,
                metrics=frontmatter.AttemptMetrics(
                    words_total=int(m["words_total"]),
                    speech_rate_wpm=float(m["speech_rate_wpm"]),
                    filler_words_count=int(m["filler_words_count"]),
                    filler_density_per_100_words=float(m["filler_density_per_100_words"]),
                    pauses_count=int(m["pauses_count"]),
                    mean_pause_ms=float(m["mean_pause_ms"]),
                    self_corrections_count=int(m["self_corrections_count"]),
                ),
            )
        )
    return attempts


def _vad_settings_for(engine_name: str, context: TranscriptionContext) -> dict | None:
    """VAD settings to record in provenance, or None when no VAD ran.

    Only the Whisper path runs VAD (Parakeet does not hallucinate on silence), and
    only when the context requested it. Records the exact tunables that ran (FR-007).
    """
    if engine_name == "whisper" and context.use_vad:
        from speakloop.asr import vad

        return vad.vad_settings()
    return None


def run_session(
    question: Question,
    *,
    tts_engine=None,
    play_fn=None,
    asr_engine: ASREngine | None = None,
    record_fn: Callable | None = None,
    grammar_analyzer=None,
    coach=None,
    console: Console | None = None,
    sessions_dir: Path | None = None,
    scratch_dir: Path | None = None,
    now=datetime.now,
    asr_engine_name: str | None = None,
    asr_model_id: str | None = None,
    asr_fell_back: bool = False,
) -> SessionResult:
    """Run a full session for one Question; return the report path + Session.

    The report is written exactly as before; the populated in-memory ``Session``
    is returned alongside (data-model §D) so the caller can drive the debrief
    without re-reading the file. Raises AbortedError on SIGINT.
    """
    console = console or Console()
    sessions_dir = Path(sessions_dir or paths.sessions_dir())
    sessions_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir = Path(scratch_dir or sessions_dir / ".tmp-audio")
    scratch_dir.mkdir(parents=True, exist_ok=True)

    abort.reset()
    abort.install_signal_handler(sessions_dir)

    if tts_engine is not None and play_fn is not None:
        q_wav = tts_engine.synthesize(question.question, voice=question.voice_override)
        a_wav = tts_engine.synthesize(question.ideal_answer, voice=question.voice_override)
        console.print(f"\n[bold]Listening to question: {question.id}[/bold]")
        play_fn(q_wav)
        console.print("[bold]Ideal answer:[/bold]")
        play_fn(a_wav)

    if asr_engine is None:
        from speakloop.asr.parakeet_engine import ParakeetEngine

        asr_engine = ParakeetEngine()
    if record_fn is None:
        record_fn = recorder.record

    # Per-session domain biasing (FR-003/FR-004): build once, inject into every
    # transcription. Engines that can't use it (Parakeet) ignore it.
    from speakloop.asr import domain_context

    context = domain_context.build_context(question)

    early_exit_event = threading.Event()
    transcripts: list[Transcript] = []
    try:
        for ordinal in (1, 2, 3):
            if abort.abort_event.is_set():
                raise AbortedError()
            early_exit_event.clear()
            _, transcript = _do_attempt(
                ordinal,
                record_fn=record_fn,
                asr_engine=asr_engine,
                early_exit_event=early_exit_event,
                console=console,
                scratch_dir=scratch_dir,
                context=context,
            )
            transcripts.append(transcript)
    except AbortedError:
        abort.cleanup_tmp_files(sessions_dir)
        # FR-016: clear partial attempt-*.wav files so the abort leaves
        # no intermediate audio on disk either.
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)
        raise

    started_at = now()
    attempts = _build_attempts(transcripts)

    grammar_patterns: list[frontmatter.GrammarPattern] = []
    phase: str = "B"
    phase_c_error: str | None = None
    if grammar_analyzer is not None:
        try:
            grammar_patterns = grammar_analyzer(transcripts)
            phase = "C"
        except Exception as e:
            # Persist the failure into the report (phase_c_error) so it is
            # diagnosable from the saved file alone, not just transient console.
            phase_c_error = f"{type(e).__name__}: {e}"
            console.print(
                f"[yellow]Grammar analyzer failed: {e}. Falling back to Phase-B interim report.[/yellow]"
            )

    # 009: cloud coaching — a SECOND, additive call after the grammar analyzer.
    # Runs ONLY after a SUCCESSFUL grammar analysis (phase == "C"); a degraded
    # grammar step (phase_c_error) skips coaching too. `coach` is None in local
    # mode, so this whole block is a no-op off the --cloud path. Any failure
    # degrades gracefully: no coaching section, a non-fatal `coach_error` note,
    # the rest of the report intact — the grammar report is never blocked.
    coaching: str | None = None
    coach_error: str | None = None
    if coach is not None and phase == "C":
        try:
            coaching = coach(question.question, transcripts, grammar_patterns)
        except Exception as e:  # noqa: BLE001 — coaching is best-effort; never crash
            coach_error = f"{type(e).__name__}: {e}"
            console.print(
                f"[yellow]Coaching step failed: {e}. The grammar report is unaffected.[/yellow]"
            )

    # ASR provenance (FR-007), recorded additively only when the caller names the
    # engine that ran (the CLI / engine selection supplies engine_name + model_id
    # + fell_back). Legacy callers omit these → asr stays None → report unchanged.
    asr_provenance = None
    if asr_engine_name is not None:
        asr_provenance = frontmatter.AsrProvenance(
            engine=asr_engine_name,
            model=asr_model_id or "",
            initial_prompt=context.initial_prompt,
            initial_prompt_sha256=context.initial_prompt_sha256,
            vad=_vad_settings_for(asr_engine_name, context),
            fell_back=asr_fell_back,
        )

    date_str = started_at.date().isoformat()
    report_path = markdown_writer.next_available_path(sessions_dir, date_str, question.id)
    session = frontmatter.Session(
        session_id=f"{date_str}-{question.id}",
        started_at=started_at,
        question_id=question.id,
        question_text=question.question,
        ideal_answer=question.ideal_answer,
        attempts=attempts,
        grammar_patterns=grammar_patterns,
        generated_by_phase=phase,
        # Deterministic, persisted narrative + Top priority (FR-008). Computed
        # for every phase: a Phase-B report still carries fluency-only guidance.
        cross_attempt_narrative=narrative.build_narrative(attempts, grammar_patterns),
        top_priority=narrative.select_top_priority(grammar_patterns, attempts),
        asr=asr_provenance,
        phase_c_error=phase_c_error,
        coaching=coaching,
        coach_error=coach_error,
    )
    body = report_builder.build(session)
    markdown_writer.write_atomic(report_path, body)
    console.print(f"[green]Report written:[/green] {report_path}")
    return SessionResult(report_path=report_path, session=session)
