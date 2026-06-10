"""Orchestrator for the 4/3/2 attempt loop.

State machine: `listening → attempt_1 → attempt_2 → attempt_3 → analyzing → reporting → done`.
A SIGINT at any state up to and including `reporting` aborts cleanly without writing a report.
"""

from __future__ import annotations

import contextlib
import os
import select
import shutil
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
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
from speakloop.triage import hallucination as _halluc

# Default time budget (seconds) for a spoken follow-up answer (P1, FR-002).
FOLLOWUP_BUDGET_SECONDS = 60


@dataclass
class Runners:
    """Injected Interview Loop LLM runners (010), all over ONE engine instance.

    Built once in ``cli/practice.py`` (local or ``--cloud``) and passed into
    ``run_session``. Each is optional so a slice that is not yet present (or a
    missing local model) simply leaves its capability off — the session still
    runs. Signatures:

    * ``mishearing(real_text: str) -> list[TriagedSpan]`` (P4 enrichment; [] on failure)
    * ``followups(question_text: str, transcripts: list[Transcript]) -> list[dict]`` (P1)
    * ``consistency(artifact: str, ideal_answer: str) -> str | None`` (P4; wired in US4)
    """

    mishearing: Callable | None = None
    followups: Callable | None = None
    consistency: Callable | None = None
    # P2c: drill(top_error_label: str) -> list[warmup.DrillItem]
    drill: Callable | None = None
    # P3: keypoints(question_text, ideal_answer, question_type) -> KeyPointSet dict
    keypoints: Callable | None = None
    # P3: coverage(key_points, transcripts, ideal_answer) -> {attempts, content_errors}
    coverage: Callable | None = None


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
    # Override the engine-reported duration with the wall-clock recording duration,
    # preserving the per-segment decode signals + VAD regions (010 P4 triage needs
    # them) — they were previously dropped here.
    transcript = Transcript(
        text=transcript.text,
        words=transcript.words,
        audio_duration_seconds=duration,
        segments=transcript.segments,
        vad_regions=transcript.vad_regions,
    )
    return duration, transcript


def _build_attempts(
    transcripts: list[Transcript],
) -> list[frontmatter.Attempt]:
    attempts: list[frontmatter.Attempt] = []
    for i, t in enumerate(transcripts, start=1):
        # 010 P4: when triage supplied real-speech regions, metrics are computed
        # over them only (hallucinated/silence spans excluded). Empty regions
        # (legacy / Parakeet) → byte-identical to before.
        m = compute_all(t, vad_regions=t.vad_regions or None)
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


def _metrics_dict(m: dict) -> dict:
    """Shape a compute_all() result into the frontmatter metrics dict."""
    return {
        "words_total": int(m["words_total"]),
        "speech_rate_wpm": float(m["speech_rate_wpm"]),
        "filler_words_count": int(m["filler_words_count"]),
        "filler_density_per_100_words": float(m["filler_density_per_100_words"]),
        "pauses_count": int(m["pauses_count"]),
        "mean_pause_ms": float(m["mean_pause_ms"]),
        "self_corrections_count": int(m["self_corrections_count"]),
    }


def _patterns_to_dicts(patterns: list[frontmatter.GrammarPattern]) -> list[dict]:
    """Minimal serialisation of follow-up grammar patterns for the report + trends.

    Tagged ``from_followup`` so cross-session aggregation can attribute them (FR-036)."""
    out: list[dict] = []
    for p in patterns:
        out.append(
            {
                "label": p.label,
                "occurrence_count": int(p.occurrence_count),
                "from_followup": True,
                "evidence": [
                    {"quote": ev.get("quote", ""), "corrected": ev.get("corrected", "")}
                    for ev in p.evidence
                ],
            }
        )
    return out


def _run_follow_ups(
    question: Question,
    real_transcripts: list[Transcript],
    *,
    runners: Runners | None,
    grammar_analyzer,
    asr_engine: ASREngine,
    record_fn,
    tts_engine,
    play_fn,
    context: TranscriptionContext | None,
    scratch_dir: Path,
    early_exit_event: threading.Event,
    console: Console,
) -> list[dict]:
    """P1: ask 1–2 unscripted, spoken follow-ups grounded in the learner's own
    words; record + transcribe + analyze each (FR-001..FR-006).

    No-op (returns []) unless a follow-up runner AND TTS playback are available, so
    every existing caller (which passes neither) is unaffected. Live-audio behavior
    (TTS pronunciation, recording, ~10s latency, silence timeout) is validated by
    the manual voice smoke test — it cannot be exercised automatically."""
    if not (runners and runners.followups and tts_engine is not None and play_fn is not None):
        return []
    try:
        specs = runners.followups(question.question, real_transcripts) or []
    except Exception as e:  # noqa: BLE001 — follow-ups are best-effort; never crash
        console.print(f"[yellow]Follow-up generation failed: {e}. Skipping follow-ups.[/yellow]")
        return []
    if not specs:
        console.print("[dim]No probe-worthy material for a follow-up this round.[/dim]")
        return []

    follow_ups: list[dict] = []
    for i, spec in enumerate(specs[:2], start=1):
        if abort.abort_event.is_set():
            # Abort during follow-ups: stop asking more, but DON'T discard the
            # session — the 3 attempts + analysis are already complete, so
            # run_session still writes that report (never lose finished work).
            break
        q_text = str((spec or {}).get("question", "")).strip()
        if not q_text:
            continue
        console.print(f"\n[bold]Follow-up {i}:[/bold] {q_text}")
        try:
            play_fn(tts_engine.synthesize(q_text, voice=question.voice_override))
        except Exception as e:  # noqa: BLE001 — TTS/playback failure → skip this follow-up
            console.print(f"[yellow]Could not play follow-up {i}: {e}. Skipping.[/yellow]")
            continue
        wav_path = scratch_dir / f"followup-{i}.wav"
        early_exit_event.clear()
        try:
            duration = record_fn(
                wav_path,
                time_budget_seconds=FOLLOWUP_BUDGET_SECONDS,
                early_exit_event=early_exit_event,
            )
        except Exception as e:  # noqa: BLE001 — device failure (not silence) → skip
            console.print(f"[yellow]Recording failed for follow-up {i}: {e}. Skipping.[/yellow]")
            continue
        transcript = asr_engine.transcribe(wav_path, context=context)
        triaged = _halluc.filter_hallucinations(transcript)
        answered = bool(triaged.real_text.strip())
        entry: dict = {
            "index": i,
            "question_text": q_text,
            "probe_ref": str((spec or {}).get("probe_ref") or (spec or {}).get("probe_type") or ""),
            "answered": answered,
            "transcript": triaged.real_text,
        }
        if answered:
            real = Transcript(
                text=triaged.real_text,
                words=transcript.words,
                audio_duration_seconds=duration,
                vad_regions=triaged.real_regions,
            )
            entry["metrics"] = _metrics_dict(compute_all(real, vad_regions=triaged.real_regions or None))
            if grammar_analyzer is not None:
                # follow-up grammar is best-effort; a failure just omits it
                with contextlib.suppress(Exception):
                    entry["grammar_patterns"] = _patterns_to_dicts(grammar_analyzer([real]))
        else:
            console.print(f"[dim]No answer to follow-up {i} (timed out).[/dim]")
        follow_ups.append(entry)
    return follow_ups


WARMUP_ITEM_BUDGET_SECONDS = 20  # 3 items ≈ 30–60s total (Key Definitions)


def _top_recurring_error(store, *, window: int = 5, min_total: int = 2) -> str | None:
    """The grammar-pattern label with the highest recent total (Key Definitions)."""
    best_label, best_total = None, 0
    for label, series in (getattr(store, "patterns", None) or {}).items():
        total = sum(int(c) for _, c in series[-window:])
        if total > best_total:
            best_label, best_total = label, total
    return best_label if best_total >= min_total else None


def _run_warmup(
    question: Question,
    *,
    runners: Runners | None,
    store,
    asr_engine: ASREngine,
    record_fn,
    tts_engine,
    play_fn,
    context: TranscriptionContext | None,
    scratch_dir: Path,
    early_exit_event: threading.Event,
    console: Console,
) -> dict | None:
    """P2c: a 30–60s spoken warm-up drill from the learner's top recurring error,
    with immediate per-item pass/fail. No-op (None) unless a drill runner + TTS +
    store are present. Skips gracefully when there's no qualifying error or
    generation fails (FR-016/FR-017). Live audio = smoke-validated."""
    if not (runners and runners.drill and tts_engine is not None and play_fn is not None and store is not None):
        return None
    top_error = _top_recurring_error(store)
    if not top_error:
        return {"skipped_reason": "no_recurring_error", "items": []}
    try:
        items = runners.drill(top_error)
    except Exception as e:  # noqa: BLE001 — warm-up is best-effort; never block the session
        console.print(f"[yellow]Warm-up generation unavailable: {e}. Skipping warm-up.[/yellow]")
        return {"target_pattern": top_error, "skipped_reason": "generation_unavailable", "items": []}
    if not items:
        return {"target_pattern": top_error, "skipped_reason": "generation_unavailable", "items": []}

    from speakloop.warmup.drill import judge_item

    console.print(f"\n[bold]Warm-up[/bold] (30–60s) — exercising: [cyan]{top_error}[/cyan]")
    results: list[dict] = []
    for i, item in enumerate(items, start=1):
        if abort.abort_event.is_set():
            break
        console.print(f"[dim]Say:[/dim] {item.target_sentence}")
        try:
            play_fn(tts_engine.synthesize(item.target_sentence, voice=question.voice_override))
        except Exception:  # noqa: BLE001 — playback failure → mark incomplete, continue
            results.append({"index": i, "target_sentence": item.target_sentence, "result": "incomplete"})
            continue
        wav_path = scratch_dir / f"warmup-{i}.wav"
        early_exit_event.clear()
        try:
            record_fn(wav_path, time_budget_seconds=WARMUP_ITEM_BUDGET_SECONDS, early_exit_event=early_exit_event)
            transcript = asr_engine.transcribe(wav_path, context=context)
            verdict = judge_item(item, transcript.text)
        except Exception:  # noqa: BLE001 — device failure → incomplete, continue
            verdict = "incomplete"
        console.print(f"  → [bold]{verdict}[/bold]")
        results.append({"index": i, "target_sentence": item.target_sentence, "result": verdict})
    return {"target_pattern": top_error, "items": results}


def run_session(
    question: Question,
    *,
    tts_engine=None,
    play_fn=None,
    asr_engine: ASREngine | None = None,
    record_fn: Callable | None = None,
    grammar_analyzer=None,
    coach=None,
    runners: Runners | None = None,
    listen_in_session: bool = False,
    store_path: Path | None = None,
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

    # The in-session listen block is opt-in (``listen_in_session``). The CLI does
    # its own listen loop before calling run_session and passes tts_engine/play_fn
    # only to drive the follow-up stage, so it leaves this False to avoid a
    # double-play. (010: gated; previously fired whenever tts_engine+play_fn were set.)
    if listen_in_session and tts_engine is not None and play_fn is not None:
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

    # 010 P2: load the derived store (top recurring error for the warm-up + the SRS
    # schedule update after the session). Only when store_path is provided — the CLI
    # passes one; tests omit it → no store I/O and no warm-up (legacy behavior).
    store = None
    if store_path is not None:
        from speakloop.store import io as _store_io

        store = _store_io.load(store_path)

    warmup_result = _run_warmup(
        question,
        runners=runners,
        store=store,
        asr_engine=asr_engine,
        record_fn=record_fn,
        tts_engine=tts_engine,
        play_fn=play_fn,
        context=context,
        scratch_dir=scratch_dir,
        early_exit_event=early_exit_event,
        console=console,
    )

    transcripts: list[Transcript] = []
    try:
        for ordinal in (1, 2, 3):
            if abort.abort_event.is_set():
                raise AbortedError()
            if ordinal == 3:
                # 010 P3/P5 (FR-022): state the final-round content goal before the
                # last attempt — type-aware (STAR components for behavioral).
                goal_unit = (
                    "STAR components"
                    if (getattr(question, "type", None) == "behavioral")
                    else "key points"
                )
                console.print(
                    f"[bold]Final round — goal: cover all {goal_unit} within the time budget.[/bold]"
                )
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

    # 010 P4: deterministic ASR-hallucination triage BEFORE any analysis. Drops
    # phantom/silence spans so no hallucination text reaches grammar evidence or
    # metrics (SC-003/FR-028) — works offline, independent of the LLM. Real-speech
    # regions feed metrics; mishearings (LLM enrichment) become pronunciation flags.
    triaged = [_halluc.filter_hallucinations(t) for t in transcripts]
    real_transcripts = [
        Transcript(
            text=tr.real_text,
            words=t.words,
            audio_duration_seconds=t.audio_duration_seconds,
            vad_regions=tr.real_regions,
        )
        for t, tr in zip(transcripts, triaged, strict=True)
    ]
    attempts = _build_attempts(real_transcripts)

    pronunciation_flags: list[dict] = []
    mishearing_runner = runners.mishearing if runners else None
    if mishearing_runner is not None:
        for ordinal, tr in enumerate(triaged, start=1):
            for span in mishearing_runner(tr.real_text):
                pronunciation_flags.append(
                    {
                        "attempt_ordinal": ordinal,
                        "heard": span.heard,
                        "likely_intended": span.likely_intended,
                        "signal": span.signal,
                    }
                )
    triage_summary = {
        "real": sum(len(tr.real_regions) for tr in triaged),
        "mishearing": len(pronunciation_flags),
        "hallucination_dropped": sum(len(tr.dropped) for tr in triaged),
    }

    grammar_patterns: list[frontmatter.GrammarPattern] = []
    phase: str = "B"
    phase_c_error: str | None = None
    analysis_pending: bool = False
    if grammar_analyzer is not None:
        try:
            grammar_patterns = grammar_analyzer(real_transcripts)
            phase = "C"
        except Exception as e:
            # Persist the failure into the report (phase_c_error) so it is
            # diagnosable from the saved file alone, not just transient console.
            # 010: also mark analysis_pending so `speakloop resume` can re-run the
            # analysis later over the preserved transcripts (FR-035/FR-035a).
            phase_c_error = f"{type(e).__name__}: {e}"
            analysis_pending = True
            console.print(
                f"[yellow]Grammar analyzer failed: {e}. Falling back to Phase-B interim report.[/yellow]"
            )

    # 010 P3: content coverage + content errors (one LLM call over all attempts),
    # using key points derived from the ideal answer (hash-versioned, cached in the
    # store). Runs only after a successful grammar analysis; degrades gracefully.
    coverage_records: list[dict] = []
    content_errors: list[dict] = []
    key_points_set: dict | None = None
    coverage_aggregate: float | None = None
    if runners and runners.keypoints and runners.coverage and phase == "C":
        try:
            from speakloop.coverage import keypoints as _kp

            qtype = getattr(question, "type", None) or "definition"
            khash = _kp.ideal_answer_hash(question.ideal_answer)
            cached = None
            version = 1
            if store is not None:
                by_hash = store.key_points.get(question.id) or {}
                cached = by_hash.get(khash)
                if cached is None and by_hash:
                    version = max((s.get("version", 0) for s in by_hash.values()), default=0) + 1
            if cached is not None:
                key_points_set = cached
            else:
                points = runners.keypoints(question.question, question.ideal_answer, qtype)
                key_points_set = {
                    "version": version,
                    "ideal_answer_hash": khash,
                    "question_type": qtype,
                    "points": points,
                }
                if store is not None:
                    store.key_points.setdefault(question.id, {})[khash] = key_points_set
            result = runners.coverage(
                key_points_set["points"], real_transcripts, question.ideal_answer,
                key_points_set["version"],
            )
            coverage_records = result.attempt_records
            content_errors = result.content_errors
            coverage_aggregate = result.final_aggregate
        except Exception as e:  # noqa: BLE001 — coverage is best-effort; never crash
            analysis_pending = True
            console.print(f"[yellow]Coverage scoring failed: {e}. Coverage skipped.[/yellow]")

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
            coaching = coach(question.question, real_transcripts, grammar_patterns)
        except Exception as e:  # noqa: BLE001 — coaching is best-effort; never crash
            coach_error = f"{type(e).__name__}: {e}"
            console.print(
                f"[yellow]Coaching step failed: {e}. The grammar report is unaffected.[/yellow]"
            )
        # 010 P4 (FR-027): the coach is the fact-bearing generated artifact (it can
        # invent a wrong exception name etc.) and deliberately never saw the ideal
        # answer, so consistency-check it against the ideal answer BEFORE writing —
        # correct it, or drop it entirely rather than show a contradiction (SC-004).
        if coaching and runners and runners.consistency:
            try:
                checked = runners.consistency(coaching, question.ideal_answer)
            except Exception as e:  # noqa: BLE001 — never block the report
                checked = None
                coach_error = coach_error or f"consistency check failed: {e}"
            if checked is None:
                coaching = None
                coach_error = coach_error or "coaching withheld: failed the consistency check"
                console.print(
                    "[yellow]Coaching withheld: it contradicted the reference answer "
                    "and could not be safely corrected.[/yellow]"
                )
            else:
                coaching = checked

    # 010 P1: interactive follow-ups — spoken, grounded in the learner's own words,
    # recorded + analyzed. No-op unless a follow-up runner + TTS playback are
    # injected (so existing callers are unaffected). Live-audio = smoke-validated.
    follow_ups = _run_follow_ups(
        question,
        real_transcripts,
        runners=runners,
        grammar_analyzer=grammar_analyzer,
        asr_engine=asr_engine,
        record_fn=record_fn,
        tts_engine=tts_engine,
        play_fn=play_fn,
        context=context,
        scratch_dir=scratch_dir,
        early_exit_event=early_exit_event,
        console=console,
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

    # 010 P2b: grade the session (only when grammar actually ran — a degraded /
    # no-model session stays un-graded, FR-035a). Coverage-primary in P3; here the
    # grade falls back to grammar severity.
    from speakloop.srs import grade as _srs_grade

    answer_grade = None
    if phase == "C":
        answer_grade = _srs_grade.grade_session(
            coverage_aggregate=coverage_aggregate,  # None → grammar-severity fallback
            content_error_count=len(content_errors),
            grammar_patterns=grammar_patterns,
        )

    # 010 P2a: fold this session's patterns into the store and derive the trend
    # lines for the patterns shown this session (FR-008).
    pattern_trends: dict | None = None
    if store is not None:
        from speakloop.trends.aggregator import format_series

        iso = started_at.date().isoformat()
        for p in grammar_patterns:
            label = (p.label or "").strip()
            if label:
                store.patterns.setdefault(label, []).append([iso, int(p.occurrence_count)])
        trends = {
            (p.label or "").strip(): format_series(store.patterns[(p.label or "").strip()], window=3)
            for p in grammar_patterns
            if (p.label or "").strip() and store.patterns.get((p.label or "").strip())
        }
        pattern_trends = trends or None

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
        # 010 additive: question type (P5), triage outputs (P4), follow-ups (P1),
        # and the degradation flag. All default-empty for legacy/local callers.
        question_type=getattr(question, "type", None) or "definition",
        warmup=warmup_result,
        answer_grade=answer_grade,
        pattern_trends=pattern_trends,
        coverage=coverage_records,
        content_errors=content_errors,
        key_points=key_points_set,
        follow_ups=follow_ups,
        pronunciation_flags=pronunciation_flags,
        # Emit the triage summary only when there is something to summarize (a
        # dropped hallucination or a pronunciation flag), so a clean session stays
        # byte-identical (additive-optional key, SC-012).
        triage_summary=(
            triage_summary
            if triage_summary.get("hallucination_dropped", 0) > 0 or pronunciation_flags
            else None
        ),
        analysis_pending=analysis_pending,
    )
    body = report_builder.build(session)
    markdown_writer.write_atomic(report_path, body)
    console.print(f"[green]Report written:[/green] {report_path}")

    # 010 P2b: advance the SRS schedule in the store (only on a graded session) and
    # persist the store atomically. The report (the source of truth) is already
    # written, so a store-write failure never costs the session.
    if store is not None and store_path is not None:
        # Advance only on a graded, complete session — a degraded/analysis-pending
        # session stays due and un-graded so `resume` can re-grade it (FR-035a).
        if answer_grade is not None and not analysis_pending:
            from speakloop.srs import schedule as _srs_schedule
            from speakloop.store.model import ScheduleEntry

            entry = store.schedule.get(question.id) or ScheduleEntry(question_id=question.id)
            store.schedule[question.id] = _srs_schedule.next_due(
                entry, answer_grade, today=started_at.date()
            )
        from speakloop.store import io as _store_io

        _store_io.save_atomic(store_path, store)

    return SessionResult(report_path=report_path, session=session)
