"""Orchestrator for the 4/3/2 attempt loop.

State machine: `listening → attempt_1 → attempt_2 → attempt_3 → analyzing → reporting → done`.
A SIGINT at any state up to and including `reporting` aborts cleanly without writing a report.
"""

from __future__ import annotations

import contextlib
import io
import queue
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
from speakloop.feedback.timings import StageTimer
from speakloop.metrics import compute_all
from speakloop.sessions import abort, session_ui, timer
from speakloop.sessions import analysis as _analysis
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


@dataclass
class PronunciationDrills:
    """Injected read-aloud pronunciation-drill capability (016).

    Built once in ``cli/practice.py`` ONLY after the safety gate permitted it and the user
    opted in (so constructing this implies the model is present + safe to load). ``scorer``
    is a ``pronunciation.PronunciationScorer`` (duck-typed here so the coordinator imports no
    engine package); ``bank`` is a ``pronunciation.DrillBank``. None ⇒ no drills (every
    existing caller passes nothing → the drill stage is a no-op, byte-identical).
    """

    scorer: object
    bank: object
    engine_note: str = ""
    # 017: hear-first TTS playback toggle + bounded per-item retry budget (from loop.yaml,
    # resolved once in cli/practice.py alongside the gate decision).
    tts_playback: bool = True
    retries: int = 1


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


def _record_attempt(
    ordinal: int,
    *,
    record_fn,
    early_exit_event: threading.Event,
    console: Console,
    scratch_dir: Path,
    key_reader=None,
    ui_sleep=time.sleep,
) -> tuple[Path, float]:
    """Record one attempt and return its WAV path + wall-clock duration (no transcription).

    012/US3 (T026): transcription is deferred to a background ASR worker so it overlaps
    the NEXT attempt's recording — the recorder + analyzer are unchanged."""
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
        f"[green]✓ Attempt {ordinal}[/green] recorded — {duration:.1f}s captured."
    )
    return wav_path, duration


def _transcribe_attempt(
    wav_path: Path,
    duration: float,
    asr_engine: ASREngine,
    context: TranscriptionContext | None,
) -> Transcript:
    """Transcribe one recorded attempt, overriding the duration with the wall-clock value.

    Preserves the per-segment decode signals + VAD regions (010 P4 triage needs them).
    Run on a single background ASR worker so two Whisper jobs never run at once (FR-022)."""
    transcript = asr_engine.transcribe(wav_path, context=context)
    return Transcript(
        text=transcript.text,
        words=transcript.words,
        audio_duration_seconds=duration,
        segments=transcript.segments,
        vad_regions=transcript.vad_regions,
    )


class _BackgroundAsr:
    """A single **daemon** ASR worker so transcribe(N) overlaps record(N+1) while two Whisper
    jobs never run at once (FR-022, 012/T026).

    The worker is a daemon thread so a Ctrl-C abort never blocks interpreter exit on an
    in-flight decode (the audio is discarded on abort anyway). Jobs are processed strictly
    FIFO, so ``result(idx)`` always returns attempt-``idx``'s transcript. A non-blocking
    ``ThreadPoolExecutor`` was rejected here because its workers are non-daemon and would hang
    process exit (and could be deleted out from under by the abort cleanup)."""

    def __init__(self, asr_engine: ASREngine, context: TranscriptionContext | None) -> None:
        self._asr = asr_engine
        self._ctx = context
        self._jobs: queue.Queue = queue.Queue()
        self._results: dict[int, object] = {}
        self._events: dict[int, threading.Event] = {}
        self._thread = threading.Thread(target=self._run, name="speakloop-asr", daemon=True)
        self._thread.start()

    def submit(self, idx: int, wav_path: Path, duration: float) -> None:
        ev = threading.Event()
        self._events[idx] = ev
        self._jobs.put((idx, wav_path, duration, ev))

    def result(self, idx: int) -> Transcript:
        self._events[idx].wait()
        value = self._results[idx]
        if isinstance(value, BaseException):
            raise value
        return value  # type: ignore[return-value]

    def _run(self) -> None:
        while True:
            item = self._jobs.get()
            if item is None:
                return
            idx, wav_path, duration, ev = item
            try:
                self._results[idx] = _transcribe_attempt(wav_path, duration, self._asr, self._ctx)
            except BaseException as e:  # noqa: BLE001 — surfaced to the waiter via result()
                self._results[idx] = e
            finally:
                ev.set()

    def close(self) -> None:
        self._jobs.put(None)


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
        # First LLM call of the session (may also pay the lazy model load) — show
        # the labeled spinner so the terminal never sits silent (012, FR-002).
        with _analyzing(console, "Preparing your warm-up drill…"):
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


# 016: read-aloud pronunciation drills. Bounded (FR-024): a few base drills + a small total
# of follow-on minimal-pair drills for flagged contrasts. Per-drill recording budget is short
# (single words). The drill block is USER-PACED and runs while feedback runs in a background
# thread (run_session).
DRILL_BUDGET_SECONDS = 10
MAX_BASE_DRILLS = 4
MAX_FOLLOWON_DRILLS = 2


def _weak_contrasts_from_store(store) -> list[str]:
    """Contrast ids ordered most-weak-first from the cross-session tally (US4, FR-015/016).

    Returns ``[]`` when there is no history → ``select_drills`` falls back to the curated order.
    Defensive: tolerates a store without the derivation (an old store / None)."""
    if store is None or not hasattr(store, "weak_contrasts"):
        return []
    return store.weak_contrasts()


def _run_pronunciation_drills(
    *,
    drills: PronunciationDrills | None,
    record_fn,
    scratch_dir: Path,
    early_exit_event: threading.Event,
    console: Console,
    key_reader=None,
    ui_sleep=time.sleep,
    tts_engine=None,
    play_fn=None,
    weak_contrasts: list[str] | None = None,
) -> dict | None:
    """017: present a bounded block of user-paced read-aloud drills as a hear → say → see →
    retry loop; score each against its KNOWN canonical phonemes (FR-001..006).

    No-op (None) unless a scorer + drill bank are injected — every existing caller that passes
    nothing leaves the session byte-identical. The per-drill loop lives in the pure
    ``pronunciation.run_drill_item`` (hear-first via the injected TTS, replay-on-demand, bounded
    retry); here we only build the ``speak``/``record`` closures (TTS + the ``_record_stage`` UI),
    apply weak-sound ordering, and route a flagged base drill into bounded follow-on minimal pairs
    (016). Recording reuses ``_record_stage``; drill WAVs are discarded after scoring (privacy).
    ``DrillQuit`` (the learner pressed ``q``) and ``abort.abort_event`` both stop asking for more
    while keeping the finished attempts/feedback (the report is still written by run_session)."""
    if drills is None or getattr(drills, "scorer", None) is None or getattr(drills, "bank", None) is None:
        return None
    from speakloop import pronunciation  # light: imports no engine package

    scorer = drills.scorer
    bank = drills.bank
    base = pronunciation.select_drills(
        bank, weak_contrasts=weak_contrasts or [], max_base=MAX_BASE_DRILLS
    )
    if not base:
        return None

    tts_on = bool(getattr(drills, "tts_playback", True)) and tts_engine is not None and play_fn is not None
    retries = int(getattr(drills, "retries", 1))

    def speak(text: str) -> None:
        # Hear-first: synthesize + play the target with the existing local TTS (best-effort —
        # run_drill_item swallows any failure so a TTS hiccup never blocks the drill).
        wav = tts_engine.synthesize(text)
        play_fn(wav)

    def record(wav_path: Path, label: str) -> None:
        early_exit_event.clear()
        _record_stage(
            record_fn=record_fn,
            wav_path=wav_path,
            budget=DRILL_BUDGET_SECONDS,
            label=label,
            key_reader=key_reader,
            ui_sleep=ui_sleep,
            console=console,
            early_exit_event=early_exit_event,
        )

    console.print(
        "\n[bold]Pronunciation drills[/bold] — listen, then read each one aloud while your "
        "feedback is prepared. (Detection is reliable; any specific guess is a suggestion.)"
    )
    # The per-drill loop + bounded follow-on routing live in the pure pronunciation module
    # (DrillQuit + abort both stop asking for more; finished work is kept).
    items, _quit = pronunciation.run_drill_block(
        base,
        bank=bank,
        scorer=scorer,
        speak=speak,
        record=record,
        key_reader=key_reader,
        console=console,
        scratch_dir=scratch_dir,
        retries=retries,
        tts_on=tts_on,
        max_followons=MAX_FOLLOWON_DRILLS,
        ui_sleep=ui_sleep,
        should_abort=abort.abort_event.is_set,
    )
    return pronunciation.build_block_result(items, bank=bank, engine_note=drills.engine_note)


class _AnalysisOutputs(NamedTuple):
    grammar_patterns: list
    phase: str
    phase_c_error: str | None
    analysis_pending: bool
    pronunciation_flags: list[dict]
    coverage_records: list[dict]
    content_errors: list[dict]
    key_points_set: dict | None
    key_points_newly_derived: bool
    coverage_aggregate: float | None
    coaching: str | None
    coach_error: str | None
    analysis_mode: str
    analysis_wall_seconds: float


def _analyze(
    *,
    real_transcripts,
    triaged,
    question,
    runners,
    grammar_analyzer,
    coach,
    store,
    console,
    parallel_safe: bool,
    concurrency: int,
    stage_timer: StageTimer,
    quiet: bool = False,
) -> _AnalysisOutputs:
    """Run the post-attempt analysis and return its outputs (012, US3 — T028/T029).

    Engine-capability-aware: a single in-process model runs the calls serially; a
    parallel-safe engine runs the independent calls concurrently (cap = ``concurrency``).
    Both strategies produce the SAME outputs, assembled by the caller in a fixed order →
    a byte-identical report (FR-027). Per-call degradation is preserved exactly: a failed
    call degrades only its own dimension (FR-028). All today's gates (coverage/coaching
    only after grammar succeeds; consistency only after coaching produces output) are kept.

    Pure with respect to the store: it READS the key-point cache but does not mutate it;
    the caller writes a newly-derived key-point set (``key_points_newly_derived``) on the
    main thread afterward, so concurrency never reorders persisted state."""
    import time as _t

    mode = "concurrent" if (parallel_safe and concurrency > 1) else "serial"
    overlapped = mode == "concurrent"
    wall = 0.0
    mishearing_runner = runners.mishearing if runners else None

    # 016: when this analysis runs in a BACKGROUND thread (concurrent with the user-paced
    # read-aloud drill block), suppress the live ANALYZING spinner — two live `rich`
    # displays must never run at once. ``quiet`` swaps the spinner for a no-op context; the
    # caller passes a discard console so any degradation prints don't corrupt the drill UI
    # (the failure is still recorded in frontmatter). The non-quiet path is unchanged.
    def _spinner(_console, _msg):
        return contextlib.nullcontext() if quiet else _analyzing(_console, _msg)

    # --- Level A: grammar + mishearing (independent of each other) ---------------
    def _job_grammar():
        t0 = _t.perf_counter()
        try:
            return grammar_analyzer(real_transcripts)
        finally:
            stage_timer.record("analysis_grammar", _t.perf_counter() - t0, overlapped=overlapped)

    def _job_mishearing():
        t0 = _t.perf_counter()
        flags: list[dict] = []
        try:
            for ordinal, tr in enumerate(triaged, start=1):
                for span in mishearing_runner(tr.real_text):
                    flags.append(
                        {
                            "attempt_ordinal": ordinal,
                            "heard": span.heard,
                            "likely_intended": span.likely_intended,
                            "signal": span.signal,
                        }
                    )
            return flags
        finally:
            stage_timer.record("analysis_mishearing", _t.perf_counter() - t0, overlapped=overlapped)

    jobs_a: dict = {}
    if grammar_analyzer is not None:
        jobs_a["grammar"] = _job_grammar
    if mishearing_runner is not None:
        jobs_a["mishearing"] = _job_mishearing

    res_a: dict = {}
    if jobs_a:
        t0 = _t.perf_counter()
        with _spinner(console, "Analyzing your attempts…"):
            res_a = _analysis.run_group(jobs_a, parallel_safe=parallel_safe, concurrency=concurrency)
        wall += _t.perf_counter() - t0

    grammar_patterns: list = []
    phase = "B"
    phase_c_error: str | None = None
    analysis_pending = False
    if "grammar" in res_a:
        r = res_a["grammar"]
        if r.ok:
            grammar_patterns = r.value
            phase = "C"
        else:
            phase_c_error = f"{type(r.error).__name__}: {r.error}"
            analysis_pending = True
            console.print(
                f"[yellow]Grammar analyzer failed: {r.error}. "
                "Falling back to Phase-B interim report.[/yellow]"
            )
    pronunciation_flags: list[dict] = (
        res_a["mishearing"].value if ("mishearing" in res_a and res_a["mishearing"].ok) else []
    )

    # --- Level B: coverage-chain + coaching (only after a successful grammar pass) -
    coverage_records: list[dict] = []
    content_errors: list[dict] = []
    key_points_set: dict | None = None
    key_points_newly_derived = False
    coverage_aggregate: float | None = None
    coaching: str | None = None
    coach_error: str | None = None

    def _job_coverage():
        t0 = _t.perf_counter()
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
            newly = False
            if cached is not None:
                kps = cached
            else:
                points = runners.keypoints(question.question, question.ideal_answer, qtype)
                kps = {
                    "version": version,
                    "ideal_answer_hash": khash,
                    "question_type": qtype,
                    "points": points,
                }
                newly = True
            cov = runners.coverage(
                kps["points"], real_transcripts, question.ideal_answer, kps["version"]
            )
            return kps, newly, cov
        finally:
            stage_timer.record("analysis_coverage", _t.perf_counter() - t0, overlapped=overlapped)

    def _job_coaching():
        t0 = _t.perf_counter()
        try:
            return coach(question.question, real_transcripts, grammar_patterns)
        finally:
            stage_timer.record("analysis_coaching", _t.perf_counter() - t0, overlapped=overlapped)

    if phase == "C":
        jobs_b: dict = {}
        if runners and runners.keypoints and runners.coverage:
            jobs_b["coverage"] = _job_coverage
        if coach is not None:
            jobs_b["coaching"] = _job_coaching
        if jobs_b:
            t0 = _t.perf_counter()
            with _spinner(console, "Scoring coverage and writing your coaching…"):
                res_b = _analysis.run_group(
                    jobs_b, parallel_safe=parallel_safe, concurrency=concurrency
                )
            wall += _t.perf_counter() - t0
            if "coverage" in res_b:
                r = res_b["coverage"]
                if r.ok:
                    key_points_set, key_points_newly_derived, cov = r.value
                    coverage_records = cov.attempt_records
                    content_errors = cov.content_errors
                    coverage_aggregate = cov.final_aggregate
                else:
                    analysis_pending = True
                    console.print(
                        f"[yellow]Coverage scoring failed: {r.error}. Coverage skipped.[/yellow]"
                    )
            if "coaching" in res_b:
                r = res_b["coaching"]
                if r.ok:
                    coaching = r.value
                else:
                    coach_error = f"{type(r.error).__name__}: {r.error}"
                    console.print(
                        f"[yellow]Coaching step failed: {r.error}. "
                        "The grammar report is unaffected.[/yellow]"
                    )

        # --- Level C: consistency-check the coaching against the ideal answer -------
        if coaching and runners and runners.consistency:
            t0 = _t.perf_counter()
            try:
                checked = runners.consistency(coaching, question.ideal_answer)
            except Exception as e:  # noqa: BLE001 — never block the report
                checked = None
                coach_error = coach_error or f"consistency check failed: {e}"
            finally:
                stage_timer.record(
                    "analysis_consistency", _t.perf_counter() - t0, overlapped=False
                )
            wall += 0.0  # consistency is on the critical path; its time is in the stage record
            if checked is None:
                coaching = None
                coach_error = coach_error or "coaching withheld: failed the consistency check"
                console.print(
                    "[yellow]Coaching withheld: it contradicted the reference answer "
                    "and could not be safely corrected.[/yellow]"
                )
            else:
                coaching = checked

    return _AnalysisOutputs(
        grammar_patterns=grammar_patterns,
        phase=phase,
        phase_c_error=phase_c_error,
        analysis_pending=analysis_pending,
        pronunciation_flags=pronunciation_flags,
        coverage_records=coverage_records,
        content_errors=content_errors,
        key_points_set=key_points_set,
        key_points_newly_derived=key_points_newly_derived,
        coverage_aggregate=coverage_aggregate,
        coaching=coaching,
        coach_error=coach_error,
        analysis_mode=mode,
        analysis_wall_seconds=round(wall, 3),
    )


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
    pronunciation_drills: PronunciationDrills | None = None,
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

    # 012/US3: always-on, cheap per-stage instrumentation. The timings are saved into the
    # report frontmatter regardless of the flag; ``timings_display`` only controls the
    # terminal print (FR-018).
    stage_timer = StageTimer()

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

    # 012/US3 (T026): a single background DAEMON ASR worker so attempt-N transcription
    # overlaps attempt-(N+1) recording, while two Whisper jobs NEVER run at once (FR-022).
    # The transcript values are identical to the serial path — only WHEN they are decoded
    # changes — so the report is unaffected. Daemon so a Ctrl-C abort never blocks exit on
    # an in-flight decode; the discarded mid-decode is harmless (the audio is thrown away).
    transcripts: list[Transcript] = []
    asr_worker = _BackgroundAsr(asr_engine, context)
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
            with stage_timer.stage(f"attempt_{ordinal}_record"):
                wav_path, duration = _record_attempt(
                    ordinal,
                    record_fn=record_fn,
                    early_exit_event=early_exit_event,
                    console=console,
                    scratch_dir=scratch_dir,
                    key_reader=key_reader,
                    ui_sleep=ui_sleep,
                )
            asr_worker.submit(ordinal, wav_path, duration)
        # Wait for any still-running background transcription under a labeled state so the
        # terminal never sits silently (FR-002); the early ones already finished overlapped.
        with stage_timer.stage("transcribe_wait", overlapped=True), session_ui.working(
            console, SessionState.TRANSCRIBING, "Transcribing your attempts…"
        ):
            transcripts = [asr_worker.result(o) for o in (1, 2, 3)]
    except AbortedError:
        # The daemon worker is abandoned (it dies with the interpreter); a mid-decode that
        # races the cleanup below just errors harmlessly into a result we never read.
        abort.cleanup_tmp_files(sessions_dir)
        # FR-016: clear partial attempt-*.wav files so the abort leaves
        # no intermediate audio on disk either.
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)
        raise
    finally:
        asr_worker.close()

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

    # 012/US3 (T030): ask the follow-ups the moment the final transcript lands — BEFORE
    # the heavy analysis — so the gap from the last attempt to the first spoken follow-up
    # is minimal (SC-002). Follow-up entries are independent of the main grammar pass, so
    # the report is byte-identical regardless of this reordering. No-op unless a follow-up
    # runner + TTS playback are injected (existing callers unaffected).
    with stage_timer.stage("followups"):
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

    # 012/US3 (T028/T029): engine-capability-aware post-attempt analysis. A parallel-safe
    # engine (Claude Code / OpenRouter) runs the independent calls concurrently (≥40%
    # wall-clock reduction, SC-003); the local in-process model stays serial. Both paths
    # yield a byte-identical report (FR-027). If the user aborted during the follow-ups,
    # skip the (minute-long) analysis and write a resumable pending report rather than
    # making them wait past their Ctrl-C (never lose the finished attempts).
    pending_outs = _AnalysisOutputs(
        grammar_patterns=[], phase="B", phase_c_error=None, analysis_pending=True,
        pronunciation_flags=[], coverage_records=[], content_errors=[], key_points_set=None,
        key_points_newly_derived=False, coverage_aggregate=None, coaching=None,
        coach_error=None, analysis_mode="serial", analysis_wall_seconds=0.0,
    )
    drills_result: dict | None = None
    if abort.abort_event.is_set():
        outs = pending_outs
    elif pronunciation_drills is not None:
        # 016: run the text feedback in a BACKGROUND thread while the user does the user-paced
        # read-aloud drill block on the main thread; the report waits for BOTH (FR-002/003/004).
        # The backgrounded analysis is `quiet=True` and writes to a DISCARD console so two live
        # `rich` displays never collide; any degradation is still captured in frontmatter. The
        # drill block does not touch the store and _analyze's single store mutation stays on the
        # main thread below, so concurrency never reorders persisted state (O6 holds).
        holder: dict = {}

        def _bg_analyze() -> None:
            try:
                holder["outs"] = _analyze(
                    real_transcripts=real_transcripts, triaged=triaged, question=question,
                    runners=runners, grammar_analyzer=grammar_analyzer, coach=coach, store=store,
                    console=Console(file=io.StringIO(), force_terminal=False, width=200),
                    parallel_safe=analysis_parallel_safe, concurrency=analysis_concurrency,
                    stage_timer=stage_timer, quiet=True,
                )
            except Exception:  # noqa: BLE001 — degrade to a resumable pending report
                holder["outs"] = None

        feedback_thread = threading.Thread(
            target=_bg_analyze, name="speakloop-feedback", daemon=True
        )
        feedback_thread.start()
        drills_result = _run_pronunciation_drills(
            drills=pronunciation_drills,
            record_fn=record_fn,
            scratch_dir=scratch_dir,
            early_exit_event=early_exit_event,
            console=console,
            key_reader=key_reader,
            ui_sleep=ui_sleep,
            # 017: hear-first plays the target with the SAME injected TTS used for the
            # question/warm-up/follow-ups (no-op in tests that pass neither). weak_contrasts
            # biases drill order toward the learner's historically weak sounds (US4).
            tts_engine=tts_engine,
            play_fn=play_fn,
            weak_contrasts=_weak_contrasts_from_store(store),
        )
        # Wait for the feedback to finish — it may already be done; if not, show one live
        # spinner now that the drills (and their live display) are finished.
        if feedback_thread.is_alive():
            with session_ui.working(console, SessionState.ANALYZING, "Finishing your feedback…"):
                feedback_thread.join()
        else:
            feedback_thread.join()
        outs = holder.get("outs")
        if outs is None:
            outs = pending_outs
    else:
        outs = _analyze(
            real_transcripts=real_transcripts,
            triaged=triaged,
            question=question,
            runners=runners,
            grammar_analyzer=grammar_analyzer,
            coach=coach,
            store=store,
            console=console,
            parallel_safe=analysis_parallel_safe,
            concurrency=analysis_concurrency,
            stage_timer=stage_timer,
        )
    grammar_patterns = outs.grammar_patterns
    phase = outs.phase
    phase_c_error = outs.phase_c_error
    analysis_pending = outs.analysis_pending
    pronunciation_flags = outs.pronunciation_flags
    coverage_records = outs.coverage_records
    content_errors = outs.content_errors
    key_points_set = outs.key_points_set
    coverage_aggregate = outs.coverage_aggregate
    coaching = outs.coaching
    coach_error = outs.coach_error

    # The ONLY store mutation from analysis: cache a newly-derived key-point set. Applied
    # on the main thread after the group completes (jobs are pure), so concurrency never
    # reorders persisted state (contract analysis-concurrency.md).
    if outs.key_points_newly_derived and store is not None and key_points_set is not None:
        store.key_points.setdefault(question.id, {})[
            key_points_set["ideal_answer_hash"]
        ] = key_points_set

    triage_summary = {
        "real": sum(len(tr.real_regions) for tr in triaged),
        "mishearing": len(pronunciation_flags),
        "hallucination_dropped": sum(len(tr.dropped) for tr in triaged),
    }

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
        # 012/US3: always-on per-stage timings (additive optional; schema_version stays 1).
        timings=stage_timer.to_frontmatter(
            analysis_mode=outs.analysis_mode,
            analysis_concurrency=analysis_concurrency,
            analysis_wall_seconds=outs.analysis_wall_seconds,
        ),
        # 016: read-aloud pronunciation drill results (additive optional; None ⇒ omitted,
        # byte-identical). Distinct from `pronunciation_flags` (010 ASR mishearings).
        pronunciation_drills=drills_result,
    )
    body = report_builder.build(session)
    markdown_writer.write_atomic(report_path, body)
    console.print(f"[green]Report written:[/green] {report_path}")

    # 010 P2b: advance the SRS schedule in the store (only on a graded session) and
    # persist the store atomically. The report (the source of truth) is already
    # written, so a store-write failure never costs the session.
    next_due: str | None = None
    if store is not None and store_path is not None:
        # Advance only on a graded, complete session — a degraded/analysis-pending
        # session stays due and un-graded so `resume` can re-grade it (FR-035a).
        if answer_grade is not None and not analysis_pending:
            from speakloop.srs import schedule as _srs_schedule
            from speakloop.store.model import ScheduleEntry

            entry = store.schedule.get(question.id) or ScheduleEntry(question_id=question.id)
            advanced = _srs_schedule.next_due(entry, answer_grade, today=started_at.date())
            store.schedule[question.id] = advanced
            next_due = advanced.next_due
        # 017: fold this session's flagged pronunciation contrasts into the cross-session
        # tally (main thread, after the join — like patterns; the drill block never mutates
        # the store, so concurrency never reorders persisted state, O6). Only when drills ran.
        if drills_result:
            from speakloop.pronunciation import flagged_contrast_counts

            store.record_contrasts(
                flagged_contrast_counts(drills_result.get("items") or []),
                date_iso=started_at.date().isoformat(),
            )
        from speakloop.store import io as _store_io

        _store_io.save_atomic(store_path, store)

    # 012/US2: compact closing summary so opening the report file is optional (FR-015).
    # Degrades honestly on an analysis-pending session (FR-016).
    session_ui.render_summary(console, session, next_due=next_due)

    # 012/US3: print the per-stage breakdown when requested (display-only; the timings are
    # saved into the report regardless of the flag — instrumentation is always-on, FR-018).
    if timings_display:
        console.print(stage_timer.render())

    return SessionResult(report_path=report_path, session=session)
