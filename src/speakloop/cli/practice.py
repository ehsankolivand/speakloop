"""`speakloop practice` — listen loop in Phase A, full 4/3/2 loop in Phase B/C."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from speakloop import installer
from speakloop.audio import devices, playback
from speakloop.config import paths
from speakloop.content import QALoadError, load
from speakloop.sessions import keyboard as _keyboard
from speakloop.sessions import session_ui
from speakloop.sessions.session_ui import SessionState


def _resolve_qa_file(console: Console) -> Path:
    """Resolve the active Q&A file by precedence (004), or exit 1 with guidance.

    Precedence (paths.resolve_qa_file): --qa-file / SPEAKLOOP_QA_FILE → the personal
    override ~/.speakloop/qa.yaml (if present) → the in-repo default
    content/questions.yaml (if present). No file is auto-created on first run.
    When nothing is found, print one actionable English message naming both the
    in-repo default and the override location, then raise Exit(1) (FR-006).
    """
    resolved = paths.resolve_qa_file()
    if resolved is None:
        console.print(
            "[red]No question file found.[/red] Looked for the in-repo default "
            f"[bold]{paths.default_qa_file()}[/bold] and the personal override "
            f"[bold]{paths.qa_file_path()}[/bold].\n"
            "Add questions at the in-repo default, or create the override file "
            "(see the README section on where questions live)."
        )
        raise typer.Exit(1)
    return resolved


def _pick_question(qa_file, console: Console) -> speakloop.content.Question | None:  # noqa: F821
    """Render a numbered picker and return the chosen Question (or None on cancel).

    Invalid/out-of-range input re-prompts; only Enter / q / quit / EOF cancels —
    a typo must not exit the program (and after a session it would also throw
    away the warm resident engines)."""
    console.print()
    console.print("[bold]Available questions:[/bold]")
    for i, q in enumerate(qa_file.questions, start=1):
        first_line = q.question.strip().splitlines()[0]
        if len(first_line) > 80:
            first_line = first_line[:77] + "…"
        console.print(f"  [cyan]{i}[/cyan]. {q.id} — {first_line}")
    console.print()
    while True:
        try:
            raw = input("Pick a question by number (or q to quit): ").strip().lower()
        except EOFError:
            return None
        if raw in {"", "q", "quit"}:
            return None
        if not raw.isdigit():
            console.print("[red]Invalid input.[/red]")
            continue
        idx = int(raw) - 1
        if idx < 0 or idx >= len(qa_file.questions):
            console.print(f"[red]Out of range (1–{len(qa_file.questions)}).[/red]")
            continue
        return qa_file.questions[idx]


def _read_key() -> str:
    """Return a canonical command key: 'r', 'R', 'q', ' ' (space=next), or '' (Enter/EOF).

    Two-tier (raw cbreak on stdin then /dev/tty, else line-buffered input) via the shared
    ``sessions.keyboard.read_key_blocking``. ``_decode_listen_key`` keeps this reader's
    case-sensitive r/R table (lowercase r = replay question, R = replay ideal answer) distinct
    from the debrief menu's; EOF on the input stream → '' (treated as "next").
    """
    return _keyboard.read_key_blocking(
        decode=_decode_listen_key,
        line_parse=_parse_line_command,
        read_bytes=1,
        eof_value="",
    )


def _decode_listen_key(data: bytes) -> str:
    """Map one raw cbreak byte to a listen-loop command key (case-sensitive r/R)."""
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


def _play_listen_clip(console: Console, label: str, wav: Path, *, key_reader, play_fn) -> str:
    """Play one listen-loop clip. Returns 'replay' if `r` was pressed, else 'done'.

    Interactive (raw-capable reader): playback is skippable with `space` and replayable
    with `r`, taking effect within ~110 ms (SC-004). Non-interactive (no tty / tests):
    falls back to the injected blocking `play_fn` — today's behavior (FR-012)."""
    if not getattr(key_reader, "raw_capable", False):
        console.print(f"[dim]▶ playing {label}…[/dim]")
        play_fn(wav)
        console.print("[dim]done[/dim]")
        return "done"
    hint = session_ui.control_hint(SessionState.PLAYING)
    console.print(f"[dim]▶ playing {label}… ({hint})[/dim]")
    captured: dict = {"key": None}

    def _should_stop() -> bool:
        key = key_reader.poll()
        if key in ("space", "enter", "r"):
            captured["key"] = key
            return True
        return False

    with key_reader:
        playback.play_interruptible(wav, should_stop=_should_stop)
    return "replay" if captured["key"] == "r" else "done"


def _listen_loop(
    question, console: Console, tts_engine, play_fn, *, key_reader=None, autoplay_ideal: bool = True
) -> str:
    """Play question + ideal answer; loop on replay commands.

    Returns the canonical exit key so the caller can route Phase B:
      ' '  → space pressed → advance to attempts
      'q'  → q pressed → quit
      ''   → Enter / EOF / Ctrl-D → quit (safer default than auto-advancing)
    'r' and 'R' stay inside the loop and trigger replay. 012: clips are skippable
    mid-playback and the ideal answer's autoplay is opt-out (`autoplay_ideal`, FR-014)."""
    key_reader = key_reader if key_reader is not None else _keyboard.make_key_reader()

    def _play(label: str, wav: Path) -> None:
        while _play_listen_clip(console, label, wav, key_reader=key_reader, play_fn=play_fn) == "replay":
            console.print("[dim]↻ replay[/dim]")

    voice = question.voice_override
    console.print(f"\n[bold]Question:[/bold] {question.id}\n")
    console.print(question.question.strip())
    # Synthesize AFTER the question is on screen: a cache miss pays the lazy
    # Kokoro load here, and a blank terminal would look hung.
    console.print("[dim]Preparing audio…[/dim]")
    q_wav = tts_engine.synthesize(question.question, voice=voice)
    a_wav = tts_engine.synthesize(question.ideal_answer, voice=voice)
    _play("question", q_wav)
    console.print("\n[bold]Ideal answer:[/bold]\n")
    console.print(question.ideal_answer.strip())
    if autoplay_ideal:
        _play("ideal answer", a_wav)
    else:
        # 012/FR-014: don't force a re-listen on repeat reviews; still replayable with R.
        console.print("[dim](autoplay off — press R to hear the ideal answer)[/dim]")

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


class EngineSelectionError(ValueError):
    """Bad ``--engine``/``--cloud`` combination (unknown value or conflicting flags)."""


def resolve_engine_choice(engine: str | None, cloud: bool) -> str:
    """Resolve the analysis engine (011).

    Precedence: explicit ``--engine`` flag → loop-config ``engine:`` → built-in
    ``"local"``. ``--cloud`` is an exact alias for ``--engine openrouter``. A
    conflicting combination or an unknown value raises ``EngineSelectionError``."""
    from speakloop.config.loop_config import VALID_ENGINES

    if engine is not None:
        chosen = engine.strip().lower()
        if chosen not in VALID_ENGINES:
            raise EngineSelectionError(
                f"--engine must be one of {', '.join(VALID_ENGINES)} (got {engine!r})."
            )
        if cloud and chosen != "openrouter":
            raise EngineSelectionError(
                "--cloud is an alias for --engine openrouter and conflicts with "
                f"--engine {chosen}."
            )
        return chosen
    if cloud:
        return "openrouter"
    from speakloop.config import loop_config

    return loop_config.load().engine


# --- Pronunciation drills (016) --------------------------------------------


def _is_interactive() -> bool:
    """Whether we can prompt the user (a real terminal on stdin). Module-level so tests
    can override it without touching the process's real stdin."""
    return sys.stdin.isatty()


def _resolve_pronunciation_drills(engine_choice: str, console: Console, *, drills_flag, input_fn=input):
    """Resolve whether to offer read-aloud pronunciation drills and, if so, build the bundle.

    Returns a ``coordinator.PronunciationDrills`` to inject, or ``None`` to skip. Reads the
    persisted ``pronunciation_drills`` setting (auto/on/off), applies the ``--drills/--no-drills``
    per-run override, runs the engine+RAM safety gate (P3), offers/declines per the rules, and on
    opt-in downloads the model (via the existing resilient downloader) and builds the scorer.
    Skips cleanly on off / unsafe / decline / error. Engine imports are function-local so
    ``speakloop --help`` never loads the model (FR-012..FR-019)."""
    from speakloop.config import loop_config

    cfg = loop_config.load()
    setting = cfg.pronunciation_drills  # auto | on | off
    if drills_flag is True:
        setting = "on"
    elif drills_flag is False:
        setting = "off"
    if setting == "off":
        return None

    from speakloop.pronunciation import assess_safety

    decision = assess_safety(engine_choice, min_free_mb=cfg.pronunciation_min_free_mb)
    interactive = _is_interactive()

    if decision.safe:
        console.print(f"[cyan]Pronunciation drills[/cyan]: {decision.reason}")
        if setting == "auto":
            # Offer (default yes when safe). Non-interactive auto can't consent → skip (never force).
            if not interactive:
                console.print("[dim](non-interactive; skipping the drills offer)[/dim]")
                return None
            try:
                ans = input_fn(
                    "Do a few read-aloud drills while your feedback runs? [Y/n]: "
                ).strip().lower()
            except EOFError:
                return None
            if ans in {"n", "no"}:
                return None
        # setting == "on" → run when safe without prompting.
        return _provision_and_build_drills(console, decision, cfg, input_fn=input_fn)

    # Unsafe: warn + skip by default; offer the explicit freeze-warned override interactively.
    console.print(f"[yellow]Pronunciation drills skipped:[/yellow] {decision.reason}")
    if interactive and setting in ("auto", "on"):
        try:
            ans = input_fn(
                "Load the pronunciation model anyway? This may freeze your machine. [y/N]: "
            ).strip().lower()
        except EOFError:
            return None
        if ans in {"y", "yes"}:
            console.print(
                "[red]Override accepted — loading the pronunciation model despite the memory "
                "risk.[/red]"
            )
            return _provision_and_build_drills(console, decision, cfg, input_fn=input_fn)
    return None


def _provision_and_build_drills(console: Console, decision, cfg, *, input_fn=input):
    """Download the model (opt-in, resilient downloader) and build the scorer + drill bank.

    Returns a ``coordinator.PronunciationDrills`` bundle (carrying the 017 hear-first/retry
    config from ``cfg``), or None on decline/failure (the session continues without drills)."""
    from speakloop import installer, pronunciation
    from speakloop.installer import manifest, validator

    # Bridge the offer/override → download-consent narrative: the first time only, the model
    # is fetched once through the standard consent (size disclosure, FR-018). On a non-terminal
    # stdin that consent can't be answered, so the standard flow declines-by-default and we skip
    # cleanly — never a silent download. (When the model is already present, no prompt appears.)
    if not validator.validate(manifest.WAV2VEC2_PRONUNCIATION).ok:
        console.print(
            "[dim]Setting up pronunciation drills — the model is downloaded once "
            "(size shown next).[/dim]"
        )
    try:
        installer.ensure_pronunciation_model(console=console, input_fn=input_fn)
    except installer.InstallDeclinedError:
        console.print("[yellow]Pronunciation model download declined — skipping drills.[/yellow]")
        return None
    except installer.InstallFailedError as e:
        console.print(f"[yellow]Pronunciation model unavailable ({e}); skipping drills.[/yellow]")
        return None

    try:
        scorer = pronunciation.build_scorer()
        bank = pronunciation.load_drill_bank()
    except Exception as e:  # noqa: BLE001 — never let drill setup crash the session
        console.print(f"[yellow]Could not set up pronunciation drills ({e}); skipping.[/yellow]")
        return None

    from speakloop.config import loop_config
    from speakloop.sessions.coordinator import PronunciationDrills

    return PronunciationDrills(
        scorer=scorer,
        bank=bank,
        engine_note=decision.reason,
        # 017: hear-first playback toggle + bounded per-item retries from loop.yaml.
        tts_playback=cfg.pronunciation_tts_playback,
        retries=cfg.pronunciation_retries,
        # 017 P2: slower rate for the focused per-sound teaching beat (word in isolation).
        teach_speed=loop_config.teach_speed(cfg.pronunciation_tts_speed),
    )


def run(
    *,
    question: str | None = None,
    listen_only: bool = False,
    no_audio: bool = False,
    asr_engine_choice: str | None = None,
    cloud: bool = False,
    engine: str | None = None,
    speed: float = 1.0,
    timings: bool = False,
    drills: bool | None = None,
    tts_engine=None,
    play_fn=None,
    audio_devices=devices,
    input_fn=input,
) -> None:
    """Entry point for `speakloop practice`."""
    console = Console()

    try:
        engine_choice = resolve_engine_choice(engine, cloud)
    except EngineSelectionError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from None

    # Keep the TTS speed inside a sane range so the engine never gets a
    # nonsensical multiplier (e.g. 0 or negative). Out-of-range values are
    # clamped with one English notice rather than failing the run.
    clamped = max(0.5, min(2.0, speed))
    if clamped != speed:
        console.print(
            f"[yellow]--speed {speed} is out of range; using {clamped} "
            f"(allowed 0.5–2.0).[/yellow]"
        )
    speed = clamped

    qa_path = _resolve_qa_file(console)
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

    # 015: provision exactly what this run needs — the required base phase (aborts on
    # decline) plus the optional local Phase-C feedback model (degrades on decline).
    _provision_models(engine_choice, listen_only=listen_only, console=console)

    if tts_engine is None:
        from speakloop.tts.kokoro_engine import KokoroEngine

        tts_engine = KokoroEngine(speed=speed)
    if play_fn is None:
        play_fn = playback.play

    # 012: one key reader drives every single-key control (listen loop + session). A
    # real raw reader when a tty is reachable, else a NullKeyReader (line/timeout
    # fallback). The autoplay-ideal-answer toggle comes from loop.yaml (default on).
    from speakloop.config import loop_config as _loop_config

    key_reader = _keyboard.make_key_reader()
    autoplay_ideal = _loop_config.load().autoplay_ideal_answer
    analysis_concurrency = _loop_config.load().analysis_concurrency
    # Warm the output device once so the first clip is not delayed by the CoreAudio open.
    if getattr(key_reader, "raw_capable", False):
        playback.warm_output_device()

    # --listen-only: hear the question + ideal answer; no attempts, no debrief.
    if listen_only:
        _listen_loop(
            chosen, console, tts_engine, play_fn,
            key_reader=key_reader, autoplay_ideal=autoplay_ideal,
        )
        return

    # Phase B/C: advance to attempts. Pre-check microphone (FR-009).
    if audio_devices.default_input() is None:
        console.print("[red]No microphone detected. Run `speakloop doctor` for remediation.[/red]")
        raise typer.Exit(1)

    from speakloop import asr as _asr
    from speakloop import debrief
    from speakloop.sessions import coordinator

    # Construct the engine ONCE, before the loop, and inject it into every
    # session. Replay reuses this resident instance — no model reload — so the
    # next "press space to begin attempt 1" appears in < 3 s (SC-004,
    # research.md §d). The grammar analyzer closure holds a lazily-loaded,
    # memoised QwenEngine; Kokoro is already injected.
    #
    # 003: build_engine resolves the default Whisper (research §B.2) or the
    # `--asr-engine` choice, probes the load eagerly (the cold load is outside the
    # timed attempt loop → warm model per SC-D, research §c), and falls back to
    # Parakeet on load failure with one English line (FR-009/SC-F). The engine
    # packages are imported function-local inside the wrapper files, so
    # `speakloop --help` never loads them (Principle VIII).
    selection = _asr.build_engine(asr_engine_choice)
    asr_engine = selection.engine
    asr_engine_name = selection.engine_name
    asr_model_id = selection.model_id
    if selection.fell_back:
        console.print(
            f"[yellow]ASR: requested engine unavailable "
            f"({selection.fallback_reason}); falling back to Parakeet.[/yellow]"
        )
    # Engine selection (011/012): local Qwen (default, offline), OpenRouter, or Claude Code.
    # Build the grammar analyzer + optional coach + runner bundle + concurrency capability
    # ONCE, before the loop, reused per session (typed fields, IMP-017).
    analysis = _build_analysis(engine_choice, console)
    grammar_analyzer = analysis.runner
    coach_runner = analysis.coach
    runners = analysis.runners
    analysis_parallel_safe = analysis.parallel_safe

    # 016: resolve the optional read-aloud pronunciation-drill capability ONCE, before the
    # timed loop (the model download/consent happens here, not mid-session). Returns a bundle
    # to inject, or None to skip (setting off / unsafe gate / declined / error). Reused on
    # REPLAY/NEW like the engines. Engine imports stay function-local (the bundle build is
    # inside `_resolve_pronunciation_drills`), so `speakloop --help` stays model-free.
    pronunciation_drills = _resolve_pronunciation_drills(
        engine_choice, console, drills_flag=drills, input_fn=input_fn
    )

    current = chosen
    need_listen = True
    while True:
        # The listen phase runs on the first question and on NEW — but NOT on
        # REPLAY, which goes straight back to the attempts (FR-025/FR-026).
        if need_listen:
            exit_key = _listen_loop(
                current, console, tts_engine, play_fn,
                key_reader=key_reader, autoplay_ideal=autoplay_ideal,
            )
            if exit_key != " ":  # q / Enter / EOF → leave practice
                return

        try:
            result = coordinator.run_session(
                current,
                asr_engine=asr_engine,
                console=console,
                grammar_analyzer=grammar_analyzer,
                coach=coach_runner,
                runners=runners,
                # 010: pass TTS + playback so the coordinator can SPEAK the warm-up +
                # follow-ups. listen_in_session stays False (the listen loop already ran
                # above), so this does not re-play the question/answer. store_path enables
                # the warm-up's top-error lookup + the SRS schedule update.
                tts_engine=tts_engine,
                play_fn=play_fn,
                store_path=paths.store_path(),
                asr_engine_name=asr_engine_name,
                asr_model_id=asr_model_id,
                asr_fell_back=selection.fell_back,
                timings_display=timings,
                key_reader=key_reader,
                analysis_parallel_safe=analysis_parallel_safe,
                analysis_concurrency=analysis_concurrency,
                pronunciation_drills=pronunciation_drills,
            )
        except coordinator.AbortedError:
            # Raised only when no report exists yet (warm-up/recording/transcribe
            # abort); an abort during follow-ups degrades inside the coordinator
            # and still writes a resumable analysis-pending report.
            console.print(
                "[yellow]Session aborted — partial recordings discarded; "
                "no report written.[/yellow]"
            )
            raise typer.Exit(130)

        choice = debrief.run(
            result.session,
            sessions_dir=result.report_path.parent,
            tts_engine=tts_engine,
            play_fn=play_fn,
            no_audio=no_audio,
            console=console,
        )

        if choice == debrief.DebriefChoice.REPLAY:
            need_listen = False  # skip the listen phase; reuse resident engines
            continue
        if choice == debrief.DebriefChoice.NEW:
            picked = _pick_question(qa_file, console)
            if picked is None:
                console.print("Bye.")
                return
            current = picked
            need_listen = True
            continue
        return  # QUIT


def _provision_models(engine_choice: str, *, listen_only: bool, console: Console) -> None:
    """Download exactly what this run needs (015).

    The base phase is REQUIRED — `--listen-only` needs Phase A (TTS); a full session needs
    Phase B (TTS + ASR) to record attempts — so a decline/failure raises `typer.Exit(1)`
    (you can't record without them). The large local Phase-C feedback model (Qwen) is
    provisioned ONLY when the local engine is active on a full session (FR-007); a cloud
    engine never triggers it, and a decline/failure DEGRADES to a recorded, resumable
    session with one notice rather than aborting (FR-009) — `_build_grammar_analyzer` then
    sees the model absent and returns None.
    """
    base_phase = "A" if listen_only else "B"
    try:
        installer.ensure_models(base_phase, console=console)
    except installer.InstallDeclinedError:
        console.print("[yellow]Model download declined; nothing to do.[/yellow]")
        raise typer.Exit(1)
    except installer.InstallFailedError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if installer.engine_needs_local_llm(engine_choice, listen_only=listen_only):
        try:
            installer.ensure_models("C", console=console)
        except installer.InstallDeclinedError:
            console.print(
                "[yellow]Local feedback model declined — this session will record but produce "
                "no grammar feedback (finish later with `speakloop resume`, or use "
                "--engine openrouter / --engine claude).[/yellow]"
            )
        except installer.InstallFailedError as e:
            console.print(
                f"[yellow]Local feedback model unavailable ({e}); recording without grammar "
                "feedback (resumable with `speakloop resume`).[/yellow]"
            )


@dataclass(frozen=True)
class GrammarAnalysis:
    """The feedback-analysis bundle for one engine (011/012), returned by the three
    ``_build_*_grammar_analyzer`` builders.

    All fields are REQUIRED (no defaults) so a builder that forgets ``engine`` fails at
    construction rather than silently degrading ``parallel_safe`` to serial — the blind spot
    the old bolted-on ``.engine``/``.runners`` attributes hid (IMP-017). ``_NO_ANALYSIS``
    (every field None) is the "no local model available" sentinel, so callers read typed
    fields uniformly: ``runner is None`` ⇒ degrade, ``parallel_safe`` ⇒ False.
    """

    runner: Callable | None  # grammar analyzer (transcripts) -> patterns
    runners: object | None  # coordinator.Runners bundle (interview loop), or None
    engine: object | None  # the LLM engine the analyzer was built over
    coach: Callable | None  # additive coaching runner (cloud/claude only), or None

    @property
    def parallel_safe(self) -> bool:
        """Whether the engine's analysis calls may run concurrently (012/FR-026)."""
        return bool(getattr(self.engine, "parallel_safe", False))


_NO_ANALYSIS = GrammarAnalysis(runner=None, runners=None, engine=None, coach=None)


def _build_analysis(engine_choice: str, console: Console) -> GrammarAnalysis:
    """Build the feedback analysis bundle ONCE for the chosen engine (011/012).

    Cloud + Claude build the grammar analyzer AND the additive coaching runner over one
    shared engine; local keeps its byte-identical build and has no coach. Returns the null
    ``_NO_ANALYSIS`` when no local Phase-C model is installed (so follow-ups/triage stay off
    and the session degrades to a resumable pending report).
    """
    if engine_choice == "openrouter":
        return _build_cloud_grammar_analyzer(console)
    if engine_choice == "claude":
        return _build_claude_grammar_analyzer(console)
    return _build_grammar_analyzer()  # local — may be _NO_ANALYSIS


def _build_grammar_analyzer() -> GrammarAnalysis:
    """Return a `GrammarAnalysis` if the local Phase-C LLM is installed; else `_NO_ANALYSIS`."""
    from speakloop.installer import manifest, validator

    if not validator.validate(manifest.QWEN3_14B_4BIT).ok:
        return _NO_ANALYSIS

    from speakloop.feedback.grammar_analyzer import analyze
    from speakloop.llm.qwen_engine import QwenEngine

    qwen = QwenEngine()

    def _runner(transcripts):
        return analyze(transcripts, qwen)

    # 010: the Interview Loop runner bundle (mishearing/consistency/follow-ups) is built
    # over the SAME engine; local has no coach (009 is cloud-only).
    return GrammarAnalysis(runner=_runner, runners=_build_runners(qwen), engine=qwen, coach=None)


# 011 P2 — the static call-site → model-tier assignment (documentation + single
# source of truth). The mapping is fixed in code; only the two tier→model aliases
# are user-overridable via loop.yaml (claude_fast_model / claude_strong_model).
# _build_runners routes mishearing + drill through fast_engine; everything else
# (incl. grammar + coach in _build_claude_grammar_analyzer) uses the strong engine.
CLAUDE_TIER_MAP = {
    "fast": ("mishearing", "drill"),
    "strong": ("followups", "keypoints", "coverage", "consistency", "grammar", "coach"),
}


def _build_runners(engine, *, fast_engine=None):
    """Build the Interview Loop LLM runners over the injected engine(s) (010, FR-039).

    Every new LLM call (mishearing triage, artifact consistency, follow-up
    generation) goes through the injected engine — no new engine client code
    (Principle V). Each loads its own seeded prompt. Returns a coordinator.Runners.

    011 model tiering: ``fast_engine`` (defaults to ``engine``) backs the cheap,
    mechanical calls — mishearing classification and drill generation — while the
    reasoning-heavy calls stay on ``engine``. For the local/OpenRouter engines
    ``fast_engine`` is left None → both tiers are the same instance → byte-identical
    to before; only the Claude Code builder passes a distinct fast engine.
    """
    if fast_engine is None:
        fast_engine = engine
    from speakloop.coverage import keypoints as _kp
    from speakloop.coverage import scoring as _cov
    from speakloop.coverage.prompts import load_coverage_prompt, load_keypoints_prompt
    from speakloop.interviewer import followups as _fu
    from speakloop.interviewer.prompts import load_followups_prompt
    from speakloop.sessions.coordinator import Runners
    from speakloop.triage import consistency as _cons
    from speakloop.triage import mishearing as _mis
    from speakloop.triage.prompts import load_consistency_prompt, load_triage_prompt
    from speakloop.warmup import drill as _drill

    triage_prompt, _ = load_triage_prompt()
    consistency_prompt = load_consistency_prompt()
    followups_prompt, _ = load_followups_prompt()
    drill_prompt, _ = _drill.load_drill_prompt()
    keypoints_prompt, _ = load_keypoints_prompt()
    coverage_prompt, _ = load_coverage_prompt()

    def _mishearing(real_text):  # cheap/mechanical → fast tier
        return _mis.detect_mishearings(real_text, fast_engine, system_prompt=triage_prompt)

    def _consistency(artifact, ideal_answer):
        verdict = _cons.check_artifact(artifact, ideal_answer, engine, system_prompt=consistency_prompt)
        return _cons.resolve(artifact, verdict)

    def _followups(question_text, transcripts):
        return _fu.generate_followups(question_text, transcripts, engine, system_prompt=followups_prompt)

    def _drill_runner(top_error_label):  # cheap/mechanical → fast tier
        return _drill.generate_drill(top_error_label, fast_engine, system_prompt=drill_prompt)

    def _keypoints(question_text, ideal_answer, question_type):
        return _kp.derive_key_points(
            question_text, ideal_answer, question_type, engine, system_prompt=keypoints_prompt
        )

    def _coverage(key_points, transcripts, ideal_answer, version):
        return _cov.score_coverage(
            key_points, transcripts, ideal_answer, engine,
            system_prompt=coverage_prompt, version=version,
        )

    return Runners(
        mishearing=_mishearing,
        followups=_followups,
        consistency=_consistency,
        drill=_drill_runner,
        keypoints=_keypoints,
        coverage=_coverage,
    )


# --- Cloud mode (008) ------------------------------------------------------

_CLOUD_DISCLOSURE = (
    "Cloud mode sends your attempt transcripts to OpenRouter for analysis. "
    "Your audio recordings and session reports never leave your device."
)


def _prompt_for_token(console: Console, *, input_fn=input) -> str:
    """First-run capture: disclose, prompt once, store. Exit 1 if declined.

    Invoking `--cloud` is the consent; this prints the one-time privacy
    disclosure (FR-018) and never blocks on a separate y/N confirmation."""
    from speakloop.llm import openrouter_credentials

    console.print(f"[yellow]{_CLOUD_DISCLOSURE}[/yellow]")
    console.print(
        "Enter your OpenRouter API token (https://openrouter.ai/keys), or press "
        "Enter to cancel and run without --cloud:"
    )
    raw = input_fn("OpenRouter token: ").strip()
    if not raw:
        console.print(
            "[red]No token provided.[/red] Set OPENROUTER_API_KEY, save the token to "
            f"{openrouter_credentials.token_path()}, or run `speakloop practice` "
            "without --cloud to use the local model."
        )
        raise typer.Exit(1)
    openrouter_credentials.store_token(raw)
    return raw


def _validated_token(console: Console, token: str, model: str, *, input_fn=input) -> str:
    """Preflight the token before the timed session (fail fast, FR-006).

    On rejection: actionable error naming both remediation paths, ONE re-prompt,
    re-store, re-check; still bad → exit. On no-connectivity → exit."""
    from speakloop.llm import openrouter_credentials
    from speakloop.llm.interface import LLMEngineError
    from speakloop.llm.openrouter_engine import OpenRouterAuthError, OpenRouterEngine

    for attempt in range(2):
        try:
            OpenRouterEngine(model=model, token=token).check_auth()
            return token
        except OpenRouterAuthError:
            console.print(
                "[red]OpenRouter rejected the token.[/red] Update it (set "
                f"OPENROUTER_API_KEY or edit {openrouter_credentials.token_path()}), "
                "or run `speakloop practice` without --cloud to use the local model."
            )
            if attempt == 0:
                token = _prompt_for_token(console, input_fn=input_fn)
                continue
            raise typer.Exit(1) from None
        except LLMEngineError as e:
            console.print(
                f"[red]Could not reach OpenRouter:[/red] {e} Check your connection, "
                "or run `speakloop practice` without --cloud."
            )
            raise typer.Exit(1) from None
    raise typer.Exit(1)


def _build_cloud_grammar_analyzer(console: Console, *, input_fn=input) -> GrammarAnalysis:
    """Return a `GrammarAnalysis` (grammar + coach runners), both backed by OpenRouter.

    Resolves the token (env > stored file; first-run prompt + store + disclosure),
    validates it once up front, loads the dedicated cloud prompts, and builds ONE
    `OpenRouterEngine` reused by both calls. Does NOT require or load the local
    Qwen model, so cloud mode works on machines that cannot fit it (US1/SC-002).
    Engine imports are function-local so `speakloop --help` stays model-free.

    `grammar_runner(transcripts) -> patterns` is the existing strict grammar
    analysis (unchanged). `coach_runner(question_text, transcripts, patterns) ->
    markdown` is the additive 009 coaching call; the coordinator runs it only
    after a successful grammar analysis and degrades gracefully on failure."""
    from speakloop.feedback import cloud_prompt as _cloud_prompt
    from speakloop.feedback import coach as _coach
    from speakloop.feedback.grammar_analyzer import analyze
    from speakloop.llm import openrouter_config, openrouter_credentials
    from speakloop.llm.openrouter_engine import OpenRouterEngine

    model = openrouter_config.resolve_model()

    token = openrouter_credentials.resolve_token()
    if token is None:
        token = _prompt_for_token(console, input_fn=input_fn)
    token = _validated_token(console, token, model, input_fn=input_fn)

    cloud_system_prompt, prompt_path = _cloud_prompt.load_cloud_prompt()
    coach_system_prompt, coach_prompt_path = _cloud_prompt.load_coach_prompt()
    engine = OpenRouterEngine(model=model, token=token)

    console.print(
        f"[cyan]Cloud mode[/cyan]: feedback via OpenRouter model [bold]{model}[/bold]. "
        "Your attempt transcripts are sent to OpenRouter (audio and reports stay local)."
    )
    console.print(f"[dim]Cloud prompt: {prompt_path} — edit to tune cloud feedback.[/dim]")
    console.print(
        f"[dim]Coach prompt: {coach_prompt_path} — edit to tune the coaching section.[/dim]"
    )

    def _grammar_runner(transcripts):
        return analyze(transcripts, engine, system_prompt=cloud_system_prompt)

    def _coach_runner(question_text, transcripts, patterns):
        return _coach.coach(
            question_text,
            transcripts,
            patterns,
            engine,
            system_prompt=coach_system_prompt,
        )

    # 010: the Interview Loop runners reuse the SAME OpenRouter engine (FR-039).
    return GrammarAnalysis(
        runner=_grammar_runner,
        runners=_build_runners(engine),
        engine=engine,  # 012/FR-026: exposes parallel_safe
        coach=_coach_runner,
    )


# --- Claude Code mode (011) ------------------------------------------------


def _build_claude_grammar_analyzer(console: Console) -> GrammarAnalysis:
    """Return a `GrammarAnalysis` (grammar + coach runners) backed by the local Claude Code CLI.

    Mirrors :func:`_build_cloud_grammar_analyzer` but drives the subscription-billed
    Claude Code product via subprocess (``ClaudeCodeEngine``). Reuses the SAME
    editable cloud prompt files (no new prompts) and the same shared seeded
    interview-loop prompts. Requires no token and makes no network preflight.

    ALWAYS returns a non-None analyzer: if Claude Code is absent or logged out, each
    analysis call raises an ``LLMEngineError`` subclass which the coordinator catches
    → ``analysis_pending`` (the session still records audio + transcripts + the
    deterministic report, resumable via ``speakloop resume --engine claude``). It does
    NOT silently fall back to the local model — matching the OpenRouter engine. Engine
    imports are function-local so ``speakloop --help`` stays model-free.
    """
    import shutil

    from speakloop.config import loop_config
    from speakloop.feedback import cloud_prompt as _cloud_prompt
    from speakloop.feedback import coach as _coach
    from speakloop.feedback.grammar_analyzer import analyze
    from speakloop.llm.claude_code_engine import ClaudeCodeEngine

    cfg = loop_config.load()
    # 011 P2 model tiering: cheap/mechanical calls (mishearing, drill) run on the
    # FAST model; reasoning-heavy calls (follow-ups, key points, coverage,
    # consistency, grammar, coach) run on the STRONG model — see CLAUDE_TIER_MAP.
    # Only the two tier→model aliases are user-overridable (loop.yaml). The per-call
    # hard timeout is also configurable (claude_timeout_seconds) — a strong model
    # like Opus running the full grammar prompt can exceed the engine's 90s baseline.
    timeout = float(cfg.claude_timeout_seconds)
    strong = ClaudeCodeEngine(
        model=cfg.claude_strong_model, effort=cfg.claude_strong_effort, timeout=timeout
    )
    fast = ClaudeCodeEngine(
        model=cfg.claude_fast_model, effort=cfg.claude_fast_effort, timeout=timeout
    )

    cloud_system_prompt, prompt_path = _cloud_prompt.load_cloud_prompt()
    coach_system_prompt, coach_prompt_path = _cloud_prompt.load_coach_prompt()

    strong_label = cfg.claude_strong_model + (
        f" @ {cfg.claude_strong_effort} effort" if cfg.claude_strong_effort else ""
    )
    fast_label = cfg.claude_fast_model + (
        f" @ {cfg.claude_fast_effort} effort" if cfg.claude_fast_effort else ""
    )
    console.print(
        f"[cyan]Claude Code engine[/cyan]: analysis runs through your local Claude Code "
        f"(strong=[bold]{strong_label}[/bold], fast=[bold]{fast_label}"
        "[/bold]), billed to your subscription. Your attempt transcripts are sent to Claude "
        "Code (audio and reports stay local)."
    )
    if shutil.which("claude") is None:
        console.print(
            "[yellow]Claude Code CLI not found on PATH.[/yellow] The session will still record "
            "and save your transcripts; analysis will be left pending. Install Claude Code and "
            "run `speakloop resume --engine claude` later."
        )
    console.print(f"[dim]Grammar prompt: {prompt_path} — edit to tune feedback.[/dim]")
    console.print(
        f"[dim]Coach prompt: {coach_prompt_path} — edit to tune the coaching section.[/dim]"
    )

    def _grammar_runner(transcripts):  # reasoning-heavy → strong
        return analyze(transcripts, strong, system_prompt=cloud_system_prompt)

    def _coach_runner(question_text, transcripts, patterns):  # reasoning-heavy → strong
        return _coach.coach(
            question_text, transcripts, patterns, strong, system_prompt=coach_system_prompt
        )

    return GrammarAnalysis(
        runner=_grammar_runner,
        runners=_build_runners(strong, fast_engine=fast),
        engine=strong,  # 012/FR-026: exposes parallel_safe
        coach=_coach_runner,
    )
