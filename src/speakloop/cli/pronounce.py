"""`speakloop pronounce` — the standalone hear → say → see → retry trainer (017, US3).

Runs the pronunciation loop OUTSIDE an interview session, user-paced. Because no feedback
engine is resident, the safety gate is the RAM-only ``assess_standalone_safety`` variant (a
configured local engine does NOT block it). It provisions only the TTS + pronunciation model
(no ASR), reuses the pure ``pronunciation.run_drill_block`` loop, biases drills toward the
learner's weak sounds, and writes NO interview report — just a closing summary + the
cross-session weak-sound tally.

All heavy imports (TTS engine, scorer build, recorder) are function-local so ``speakloop
--help`` never loads a model; ``main.py`` only imports this module inside the command body.
See ``specs/017-pronunciation-trainer/contracts/pronounce-command.md``.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from rich.console import Console

from speakloop.cli.gate_prompt import confirm_freeze_override
from speakloop.cli.gate_prompt import is_interactive as _is_interactive

# A small bounded default round size when the learner doesn't pass --limit.
DEFAULT_STANDALONE_DRILLS = 6
_STANDALONE_FOLLOWONS = 2


def _configure_debug_logging(console: Console) -> None:
    """Turn on visible diagnostics for the score path (``--debug`` / SPEAKLOOP_DEBUG). The
    score path never raises into the session, so a real failure (mic vs scoring-model) is
    otherwise flattened to a vague "could not score"; this surfaces the swallowed reason inline
    (via SPEAKLOOP_DEBUG, read by ``pronunciation.drill_runner``) AND to a log file the learner
    can share. Offline, local-only; attaches handlers once (idempotent)."""
    import logging

    os.environ["SPEAKLOOP_DEBUG"] = "1"
    logger = logging.getLogger("speakloop.pronunciation")
    logger.setLevel(logging.DEBUG)
    if any(getattr(h, "_speakloop_pron_debug", False) for h in logger.handlers):
        return
    sh = logging.StreamHandler()  # stderr
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(logging.Formatter("[pronounce] %(levelname)s %(message)s"))
    sh._speakloop_pron_debug = True  # type: ignore[attr-defined]
    logger.addHandler(sh)
    try:  # best-effort persistent log (nice for a bug report); never fatal
        from speakloop.config import paths

        log_dir = paths.ensure_dir(paths.logs_dir())
        log_path = log_dir / "pronounce-debug.log"
        fh = logging.FileHandler(log_path)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        fh._speakloop_pron_debug = True  # type: ignore[attr-defined]
        logger.addHandler(fh)
        console.print(f"[dim]Debug logging on → {log_path}[/dim]")
    except Exception:  # noqa: BLE001
        console.print("[dim]Debug logging on (console only).[/dim]")


def _gate_ok(console: Console, cfg, *, input_fn) -> bool:
    """RAM-only standalone gate (FR-011/012). Returns True to proceed (safe or freeze-warned
    override), False to skip. Never loads the model — it only decides."""
    from speakloop.pronunciation import assess_standalone_safety

    decision = assess_standalone_safety(min_free_mb=cfg.pronunciation_min_free_mb)
    if decision.safe:
        console.print(f"[cyan]Pronunciation practice[/cyan]: {decision.reason}")
        return True
    console.print(f"[yellow]Pronunciation practice skipped:[/yellow] {decision.reason}")
    return confirm_freeze_override(console, input_fn=input_fn, interactive=_is_interactive())


def _provision(console: Console, *, input_fn) -> bool:
    """Ensure the TTS (Phase A / Kokoro) + pronunciation model are present via the existing
    resilient consent/download flow. No ASR. Returns True to proceed, False on decline/failure."""
    from speakloop import installer

    try:
        installer.ensure_models("A", console=console, input_fn=input_fn)  # Kokoro TTS only
        installer.ensure_pronunciation_model(console=console, input_fn=input_fn)
    except installer.InstallDeclinedError:
        console.print(
            "[yellow]Models declined — nothing to practise. Run `speakloop pronounce` again "
            "when you're ready to download them.[/yellow]"
        )
        return False
    except installer.InstallFailedError as e:
        console.print(f"[yellow]Models unavailable ({e}); cannot run pronunciation practice.[/yellow]")
        return False
    return True


def _print_summary(console: Console, result: dict) -> None:
    s = result["summary"]
    console.print(
        f"\n[bold]Practice summary[/bold] — {s['drills']} drill(s), "
        f"{s['with_flags']} with a flagged sound"
        + (f", {s['improved_on_retry']} improved on retry" if s.get("improved_on_retry") else "")
        + "."
    )
    tricky = [t for t in (s.get("tricky_sounds") or []) if t]
    if tricky:
        console.print(f"[dim]Your trickiest sound(s) today:[/dim] {', '.join(tricky)}.")
    console.print("[green]Nice work — come back any time with `speakloop pronounce`.[/green]")


def run(
    *,
    limit: int | None = None,
    debug: bool = False,
    tts_engine=None,
    play_fn=None,
    record_fn=None,
    scorer=None,
    bank=None,
    key_reader=None,
    store_path=None,
    scratch_dir: Path | None = None,
    input_fn=input,
    console: Console | None = None,
) -> None:
    """Entry point for `speakloop pronounce`. Everything model/mic/tty is injectable for tests."""
    console = console or Console()
    if debug:
        _configure_debug_logging(console)
    from speakloop.config import loop_config, paths

    cfg = loop_config.load()
    if not _gate_ok(console, cfg, input_fn=input_fn):
        return

    # Provision only when we have to build the real engines (tests inject fakes → skip download).
    need_build = scorer is None or tts_engine is None or play_fn is None or record_fn is None or bank is None
    if need_build and not _provision(console, input_fn=input_fn):
        return

    from speakloop import pronunciation

    if scorer is None:
        scorer = pronunciation.build_scorer()
    if bank is None:
        bank = pronunciation.load_drill_bank()
    if tts_engine is None:
        from speakloop.tts.kokoro_engine import KokoroEngine

        # Slower default cadence for the trainer — the learner reported the 1.0 rate read too
        # fast to shadow (017 P2). Configurable via loop.yaml pronunciation_tts_speed.
        tts_engine = KokoroEngine(speed=cfg.pronunciation_tts_speed)
    if play_fn is None:
        from speakloop.audio import playback

        play_fn = playback.play
    if record_fn is None:
        from speakloop.audio import recorder

        record_fn = recorder.record
    if key_reader is None:
        from speakloop.sessions import keyboard

        key_reader = keyboard.make_key_reader()

    from speakloop.sessions.coordinator import DRILL_BUDGET_SECONDS, _record_stage
    from speakloop.store import io as store_io

    store_path = Path(store_path) if store_path is not None else paths.store_path()
    store = store_io.load(store_path)
    scratch_dir = Path(scratch_dir) if scratch_dir is not None else (paths.sessions_dir().parent / ".tmp-pronounce")
    scratch_dir.mkdir(parents=True, exist_ok=True)

    tts_on = bool(cfg.pronunciation_tts_playback) and tts_engine is not None and play_fn is not None
    teach_speed = loop_config.teach_speed(cfg.pronunciation_tts_speed)
    early_exit_event = threading.Event()

    def speak(text: str) -> None:
        play_fn(tts_engine.synthesize(text))

    def teach_speak(text: str) -> None:
        # The focused per-sound teaching beat: play the flagged word ALONE, even slower than
        # the drill cadence, to model the sound clearly. Falls back to normal synth if the
        # injected engine has no per-call speed (a fake in tests).
        try:
            wav = tts_engine.synthesize(text, speed=teach_speed)
        except TypeError:
            wav = tts_engine.synthesize(text)
        play_fn(wav)

    def record(wav_path: Path, label: str) -> None:
        early_exit_event.clear()
        _record_stage(
            record_fn=record_fn, wav_path=wav_path, budget=DRILL_BUDGET_SECONDS, label=label,
            key_reader=key_reader, ui_sleep=time.sleep, console=console,
            early_exit_event=early_exit_event,
        )

    max_base = limit if (limit and limit > 0) else DEFAULT_STANDALONE_DRILLS
    console.print(
        "\n[bold]Pronunciation practice[/bold] — listen, then read each one aloud. "
        "Press [bold]r[/bold] to hear it again, [bold]q[/bold] to stop.\n"
    )

    all_items: list[dict] = []
    quit_now = False
    while not quit_now:
        # In-run + cross-session weak-sound bias: re-derive from the store tally plus this run's
        # flags so each round leans into what the learner keeps missing (FR-015/016).
        weak = pronunciation.flagged_contrast_counts(all_items)
        weak_order = sorted(weak, key=lambda c: (-weak[c], c)) + store.weak_contrasts()
        seen_order: list[str] = []
        for c in weak_order:  # de-dup, preserve order
            if c not in seen_order:
                seen_order.append(c)
        base = pronunciation.select_drills(bank, weak_contrasts=seen_order, max_base=max_base)
        items, quit_now = pronunciation.run_drill_block(
            base, bank=bank, scorer=scorer, speak=speak, record=record, key_reader=key_reader,
            console=console, scratch_dir=scratch_dir, retries=cfg.pronunciation_retries,
            tts_on=tts_on, max_followons=_STANDALONE_FOLLOWONS, teach_speak=teach_speak,
        )
        all_items.extend(items)
        if quit_now or not _is_interactive():
            break
        try:
            again = input_fn("\nPractise another round? [y/N]: ").strip().lower()
        except EOFError:
            break
        if again not in {"y", "yes"}:
            break

    result = pronunciation.build_block_result(all_items, bank=bank)
    if result is None:
        console.print("[dim]No drills were completed.[/dim]")
        return
    _print_summary(console, result)

    # Update + persist the cross-session weak-sound tally (no interview report is written).
    from datetime import datetime

    store.record_contrasts(
        pronunciation.flagged_contrast_counts(all_items),
        date_iso=datetime.now().date().isoformat(),
    )
    store_io.save_atomic(store_path, store)
