"""Orchestrator for the 4/3/2 attempt loop.

State machine: `listening → attempt_1 → attempt_2 → attempt_3 → analyzing → reporting → done`.
A SIGINT at any state up to and including `reporting` aborts cleanly without writing a report.
"""

from __future__ import annotations

import contextlib
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from rich.console import Console

from speakloop.asr import ASREngine, Transcript, TranscriptionContext
from speakloop.audio import recorder
from speakloop.config import paths
from speakloop.content import Question
from speakloop.feedback import frontmatter, markdown_writer, narrative, report_builder
from speakloop.metrics import compute_all
from speakloop.sessions import abort, session_ui, timer
from speakloop.sessions import keyboard as _keyboard
from speakloop.sessions.session_ui import SessionState
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


_KEY_POLL_INTERVAL_SECONDS = 0.03


def _spawn_key_poller(
    key_reader,
    early_exit_event: threading.Event,
    stop_event: threading.Event,
    *,
    skip_event: threading.Event | None = None,
) -> threading.Thread | None:
    """Background poller: a single keypress ends the current recording early (012, FR-007).

    ``space``/``Enter`` set ``early_exit_event`` (done speaking → stop & transcribe).
    ``s`` (when ``skip_event`` is provided — the follow-up case) abandons the recording
    AND marks it skipped (FR-008). Replaces the prior canonical-mode Enter reader with a
    raw single-key ``KeyReader``.

    Returns ``None`` when the reader cannot do raw input (no tty — piped/captured stdin
    under pytest), so the session runs on the time budget exactly as before (FR-012).
    """
    if key_reader is None or not getattr(key_reader, "raw_capable", False):
        return None

    def _poll() -> None:
        with key_reader:
            while not stop_event.is_set():
                key = key_reader.poll()
                if key in ("space", "enter"):
                    early_exit_event.set()
                    return
                if key == "s" and skip_event is not None:
                    skip_event.set()
                    early_exit_event.set()
                    return
                time.sleep(_KEY_POLL_INTERVAL_SECONDS)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()
    return t


def _record_stage(
    *,
    record_fn,
    wav_path: Path,
    budget: float,
    label: str,
    key_reader,
    ui_sleep,
    console: Console,
    early_exit_event: threading.Event,
    follow_up: bool = False,
) -> tuple[float, bool]:
    """Record one clip with the countdown + ``● REC`` indicator + single-key controls.

    Returns ``(duration, skipped)``. ``skipped`` is True only when ``s`` was pressed on
    a follow-up recording (FR-008). The live indicator is visible for the whole recording
    (FR-003); the countdown (FR-004) and key poller run only when the reader can do raw
    input (interactive terminal) — otherwise this degrades to today's behavior (FR-012)."""
    interactive = getattr(key_reader, "raw_capable", False)
    if interactive:
        session_ui.countdown(console, sleep=ui_sleep)
    else:
        console.print(f"[dim]🎙 speak now ({label})…[/dim]")
    hint = session_ui.control_hint(SessionState.RECORDING, follow_up=follow_up)
    if hint:
        console.print(f"[dim]{hint}[/dim]")

    skip_event = threading.Event() if follow_up else None
    progress = session_ui.make_recording_progress(console)
    stop_helpers = threading.Event()
    ticker_thread: threading.Thread | None = None
    reader_thread: threading.Thread | None = None
    try:
        with progress:
            task_id = progress.add_task("rec", total=budget, label=label)
            tick_start = time.monotonic()

            def _ticker() -> None:
                while not stop_helpers.is_set():
                    elapsed = time.monotonic() - tick_start
                    progress.update(task_id, completed=min(elapsed, float(budget)))
                    time.sleep(0.1)

            ticker_thread = threading.Thread(target=_ticker, daemon=True)
            ticker_thread.start()
            reader_thread = _spawn_key_poller(
                key_reader, early_exit_event, stop_helpers, skip_event=skip_event
            )

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
    return duration, bool(skip_event and skip_event.is_set())


def _do_attempt(
    ordinal: int,
    *,
    record_fn,
    asr_engine: ASREngine,
    early_exit_event: threading.Event,
    console: Console,
    scratch_dir: Path,
    context: TranscriptionContext | None = None,
    key_reader=None,
    ui_sleep=time.sleep,
) -> tuple[float, Transcript]:
    budget = timer.time_budget_for(ordinal)
    console.print(f"\n[bold]Attempt {ordinal}[/bold] — budget {budget}s.")
    wav_path = scratch_dir / f"attempt-{ordinal}.wav"

    duration, _ = _record_stage(
        record_fn=record_fn,
        wav_path=wav_path,
        budget=budget,
        label=f"attempt {ordinal}",
        key_reader=key_reader,
        ui_sleep=ui_sleep,
        console=console,
        early_exit_event=early_exit_event,
    )

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


def _play_prompt(
    synthesize,
    text: str,
    voice,
    *,
    key_reader,
    play_fn,
    console: Console,
    follow_up: bool = False,
) -> str:
    """Synthesize + play a spoken prompt; return how playback ended.

    Interactive (raw-capable reader): playback is skippable (``space``), replayable
    (``r``), and — on a follow-up — abandonable (``s``); returns ``"completed"`` /
    ``"skip_followup"``. Non-interactive (no tty / tests): falls back to the injected
    blocking ``play_fn`` (today's behavior). Returns ``"error"`` on synth/playback
    failure so the caller can skip just this prompt."""
    try:
        wav = synthesize(text, voice=voice)
    except Exception:  # noqa: BLE001 — TTS failure → caller skips this prompt
        return "error"
    if not getattr(key_reader, "raw_capable", False):
        try:
            play_fn(wav)
        except Exception:  # noqa: BLE001 — playback failure → caller skips
            return "error"
        return "completed"

    from speakloop.audio import playback as _pb

    hint = session_ui.control_hint(SessionState.PLAYING, follow_up=follow_up)
    console.print(f"[dim]▶ playing… ({hint})[/dim]")
    captured: dict = {"key": None}

    def _should_stop() -> bool:
        key = key_reader.poll()
        if key in ("space", "enter", "r", "s"):
            captured["key"] = key
            return True
        return False

    while True:
        captured["key"] = None
        try:
            with key_reader:
                _pb.play_interruptible(wav, should_stop=_should_stop)
        except Exception:  # noqa: BLE001 — playback failure → caller skips
            return "error"
        key = captured["key"]
        if key == "r":
            console.print("[dim]↻ replay[/dim]")
            continue
        if key == "s" and follow_up:
            return "skip_followup"
        return "completed"


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
    key_reader=None,
    ui_sleep=time.sleep,
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
        with _analyzing(console, "Generating follow-up questions…"):
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
        played = _play_prompt(
            tts_engine.synthesize, q_text, question.voice_override,
            key_reader=key_reader, play_fn=play_fn, console=console, follow_up=True,
        )
        if played == "error":
            console.print(f"[yellow]Could not play follow-up {i}. Skipping.[/yellow]")
            continue
        if played == "skip_followup":
            # `s` during the prompt → abandon this entire follow-up, no answer recorded.
            console.print(f"[dim]Follow-up {i} skipped.[/dim]")
            follow_ups.append(
                {"index": i, "question_text": q_text,
                 "probe_ref": str((spec or {}).get("probe_ref") or (spec or {}).get("probe_type") or ""),
                 "answered": False, "transcript": "", "skipped": True}
            )
            continue
        wav_path = scratch_dir / f"followup-{i}.wav"
        early_exit_event.clear()
        try:
            duration, skipped = _record_stage(
                record_fn=record_fn,
                wav_path=wav_path,
                budget=FOLLOWUP_BUDGET_SECONDS,
                label=f"follow-up {i}",
                key_reader=key_reader,
                ui_sleep=ui_sleep,
                console=console,
                early_exit_event=early_exit_event,
                follow_up=True,
            )
        except Exception as e:  # noqa: BLE001 — device failure (not silence) → skip
            console.print(f"[yellow]Recording failed for follow-up {i}: {e}. Skipping.[/yellow]")
            continue
        if skipped:
            # `s` during the answer → abandon this follow-up (FR-008).
            console.print(f"[dim]Follow-up {i} skipped.[/dim]")
            follow_ups.append(
                {"index": i, "question_text": q_text,
                 "probe_ref": str((spec or {}).get("probe_ref") or (spec or {}).get("probe_type") or ""),
                 "answered": False, "transcript": "", "skipped": True}
            )
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
                with contextlib.suppress(Exception), _analyzing(
                    console, "Analyzing your follow-up answer…"
                ):
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


@contextlib.contextmanager
def _analyzing(console: Console, message: str):
    """Live ANALYZING spinner + elapsed timer around a slow blocking LLM call.

    Delegates to the shared ``session_ui.working`` so analysis/transcription show one
    consistent labeled state (012, FR-002/SC-007): the cloud / Claude Code engines can
    take a minute per call, and without this the terminal would sit black and look hung.
    The line is transient (cleared on completion); exceptions still propagate to the
    caller's existing degradation handling."""
    with session_ui.working(console, SessionState.ANALYZING, message):
        yield


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
    key_reader=None,
    ui_sleep=time.sleep,
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
        if _play_prompt(
            tts_engine.synthesize, item.target_sentence, question.voice_override,
            key_reader=key_reader, play_fn=play_fn, console=console,
        ) == "error":
            results.append({"index": i, "target_sentence": item.target_sentence, "result": "incomplete"})
            continue
        wav_path = scratch_dir / f"warmup-{i}.wav"
        early_exit_event.clear()
        transcript = None
        try:
            _record_stage(
                record_fn=record_fn,
                wav_path=wav_path,
                budget=WARMUP_ITEM_BUDGET_SECONDS,
                label=f"warm-up {i}",
                key_reader=key_reader,
                ui_sleep=ui_sleep,
                console=console,
                early_exit_event=early_exit_event,
            )
            transcript = asr_engine.transcribe(wav_path, context=context)
            verdict = judge_item(item, transcript.text)
        except Exception:  # noqa: BLE001 — device failure → incomplete, continue
            verdict = "incomplete"
        # Show what was actually heard so a `fail` is never a black box: the learner
        # can see whether ASR mis-heard the sentence vs. they need to repeat it.
        if transcript is not None:
            heard = transcript.text.strip() or "[i](nothing captured — speak right after the prompt)[/i]"
            console.print(f"  [dim]heard:[/dim] {heard}")
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
    analysis_parallel_safe: bool = False,
    analysis_concurrency: int = 1,
    timings_display: bool = False,
    key_reader=None,
    ui_sleep=time.sleep,
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

    # 012: a single injectable key reader drives every single-key control (skip / replay
    # / early-stop / skip-follow-up). Default resolves a real raw reader if a tty is
    # reachable, else a NullKeyReader that no-ops so the session still runs on time
    # budgets (FR-012). Tests inject a FakeKeyReader.
    if key_reader is None:
        key_reader = _keyboard.make_key_reader()

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
        key_reader=key_reader,
        ui_sleep=ui_sleep,
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
                key_reader=key_reader,
                ui_sleep=ui_sleep,
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
            with _analyzing(console, "Analyzing grammar across your attempts…"):
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
                with _analyzing(console, "Deriving key points from the model answer…"):
                    points = runners.keypoints(question.question, question.ideal_answer, qtype)
                key_points_set = {
                    "version": version,
                    "ideal_answer_hash": khash,
                    "question_type": qtype,
                    "points": points,
                }
                if store is not None:
                    store.key_points.setdefault(question.id, {})[khash] = key_points_set
            with _analyzing(console, "Scoring how well you covered the key points…"):
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
            with _analyzing(console, "Writing your coaching feedback…"):
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
        key_reader=key_reader,
        ui_sleep=ui_sleep,
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
