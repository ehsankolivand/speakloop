"""`speakloop deck` — the rescue-lines deck trainer (018, US1).

A self-graded spaced-repetition trainer for the learner's OWN corrected lines. Cards are derived
from the "Better:" corrections in past session reports (`linecards.derive_cards`) plus a bundled
starter set; each due card is drilled hear → say → see → self-mark, and the self-mark reschedules
it on the shared SRS ladder. Per-card state persists in the store's `line_cards` section.
`--export PATH` writes the whole deck as an Anki cloze-import file and exits.

TTS-only: no ASR, no phoneme scorer, no microphone. All heavy imports are function-local so
`speakloop --help` never loads a model; `main.py` imports this module only inside the command body.
See `specs/018-self-practice-modes/contracts/deck-command.md`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from speakloop.cli.gate_prompt import is_interactive as _is_interactive

# Self-mark keys → the four SRS grades (again/hard/good/easy).
_MARKS: dict[str, str] = {
    "1": "poor", "again": "poor", "a": "poor",
    "2": "fair", "hard": "fair", "h": "fair",
    "3": "good", "good": "good", "g": "good",
    "4": "strong", "easy": "strong", "e": "strong",
}


def _provision(console: Console, *, input_fn) -> bool:
    """Ensure the TTS model (Phase A / Kokoro) is present via the existing consent/download flow.
    No ASR, no pronunciation scorer. Returns True to proceed, False on decline/failure."""
    from speakloop import installer

    try:
        installer.ensure_models("A", console=console, input_fn=input_fn)
    except installer.InstallDeclinedError:
        console.print(
            "[yellow]Models declined — nothing to drill. Run `speakloop deck` again when you're "
            "ready to download the speech model (or use `speakloop deck --export PATH`).[/yellow]"
        )
        return False
    except installer.InstallFailedError as e:
        console.print(f"[yellow]Speech model unavailable ({e}); cannot run the deck.[/yellow]")
        return False
    return True


def _export(console: Console, merged: dict, path: Path) -> None:
    """Write the whole deck as an Anki cloze-import file (FR-018) and return."""
    from speakloop import linecards

    cards = [linecards.card_from_row(cid, row) for cid, row in merged.items()]
    text = linecards.to_anki(cards)
    try:
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n" if text else "", encoding="utf-8")
    except OSError as e:
        console.print(f"[red]Could not write {path}: {e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]Exported {len(cards)} card(s) to {path}[/green]")


def _drill_card(console: Console, n: int, total: int, row: dict, *, speak, tts_on, input_fn):
    """Run hear → say → see → self-mark for ONE card. Returns a grade, or None to quit."""
    console.print(f"\n[bold cyan]Card {n}/{total}[/bold cyan] — listen, then say it aloud.")
    if tts_on:
        speak(row.get("corrected", ""))
    while True:
        try:
            resp = input_fn("[Enter] reveal · [r] replay · [q] quit: ").strip().lower()
        except EOFError:
            return None
        if resp in {"q", "quit"}:
            return None
        if resp in {"r", "replay"}:
            if tts_on:
                speak(row.get("corrected", ""))
            continue
        break

    # See: reveal the target.
    if row.get("quote"):
        console.print(f"  [dim]You said:[/dim] “{row['quote']}”")
    console.print(f"  [bold]Better:[/bold] “{row.get('corrected', '')}”")
    if row.get("rule"):
        console.print(f"  [dim]Because:[/dim] {row['rule']}")

    # Self-mark.
    while True:
        try:
            mark = input_fn("How did it go?  1=again  2=hard  3=good  4=easy  (q=quit): ").strip().lower()
        except EOFError:
            return None
        if mark in {"q", "quit"}:
            return None
        grade = _MARKS.get(mark)
        if grade:
            return grade
        console.print("[yellow]Please enter 1, 2, 3, or 4 (or q to quit).[/yellow]")


def run(
    *,
    limit: int | None = None,
    export_path: Path | None = None,
    ahead: bool = False,
    tts_engine=None,
    play_fn=None,
    reports_dir: Path | None = None,
    store_path: Path | None = None,
    starter_cards=None,
    today: date | None = None,
    input_fn=input,
    console: Console | None = None,
) -> None:
    """Entry point for `speakloop deck`. Everything model/tty is injectable for tests."""
    console = console or Console()
    from speakloop import linecards
    from speakloop.config import loop_config, paths
    from speakloop.store import io as store_io

    reports_dir = Path(reports_dir) if reports_dir is not None else paths.sessions_dir()
    store_path = Path(store_path) if store_path is not None else paths.store_path()
    if starter_cards is None:
        starter_cards = linecards.load_starter_cards()
    if today is None:
        today = date.today()

    store = store_io.load(store_path)
    derived = linecards.derive_cards(reports_dir)
    merged = linecards.merge_cards(derived, starter_cards, store.line_cards)

    # --- export mode: whole-deck snapshot, no drilling, no models ---------------------------
    if export_path is not None:
        _export(console, merged, Path(export_path))
        return

    if not merged:
        console.print("[dim]No cards yet. Practise a few sessions, then come back to `speakloop deck`.[/dim]")
        return

    cfg = loop_config.load()
    cap = limit if (limit and limit > 0) else cfg.deck_daily_capacity
    due_ids = linecards.select_due(merged, today=today, capacity=cap, ahead=ahead)

    if not due_ids:
        console.print("[green]You're all caught up — no rescue-lines are due today.[/green]")
        if _is_interactive():
            try:
                ans = input_fn("Practise ahead anyway? [y/N]: ").strip().lower()
            except EOFError:
                ans = "n"
            if ans in {"y", "yes"}:
                due_ids = linecards.select_due(merged, today=today, capacity=cap, ahead=True)
        if not due_ids:
            return

    if not _is_interactive():
        console.print(
            "[yellow]The deck is self-graded and needs an interactive terminal; skipping. "
            "Use `speakloop deck --export PATH` to export your cards offline.[/yellow]"
        )
        return

    # Build the real TTS only when we must (tests inject fakes → skip download).
    need_build = tts_engine is None or play_fn is None
    if need_build and not _provision(console, input_fn=input_fn):
        return
    if tts_engine is None:
        from speakloop.tts.kokoro_engine import KokoroEngine

        tts_engine = KokoroEngine(speed=cfg.pronunciation_tts_speed)
    if play_fn is None:
        from speakloop.audio import playback

        play_fn = playback.play

    tts_on = tts_engine is not None and play_fn is not None

    def speak(text: str) -> None:
        if text:
            play_fn(tts_engine.synthesize(text))

    console.print(
        f"\n[bold]Rescue-lines deck[/bold] — {len(due_ids)} card(s) due. "
        "Hear each line, say it aloud, then mark how it went.\n"
    )

    reviewed = 0
    for idx, cid in enumerate(due_ids, start=1):
        grade = _drill_card(
            console, idx, len(due_ids), merged[cid], speak=speak, tts_on=tts_on, input_fn=input_fn
        )
        if grade is None:  # quit
            break
        merged[cid] = linecards.advance_card(merged[cid], grade, today=today)
        reviewed += 1

    # Persist per-card scheduling (main thread; no report is ever written).
    store.line_cards = merged
    store_io.save_atomic(store_path, store)
    console.print(f"\n[bold]Deck complete[/bold] — reviewed {reviewed} card(s). See you next time.")
