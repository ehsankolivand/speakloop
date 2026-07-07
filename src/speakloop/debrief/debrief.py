"""Debrief orchestrator — implements the ``DebriefRunner.run(...)`` contract.

Flow: build the view model → render in place → read the educational sections
aloud (US3) → show the r/n/q menu → return the user's choice. The report is
already written by the coordinator; this module never touches the file and never
reloads models, so the caller's replay path stays fast (SC-004).

Principle V: no engine-specific imports — TTS is used only through the injected
``TTSEngine`` + ``play_fn``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from speakloop.debrief import menu
from speakloop.debrief.menu import DebriefChoice
from speakloop.debrief.renderer import DebriefRenderer
from speakloop.debrief.view_model import build_view_model
from speakloop.feedback import frontmatter

if TYPE_CHECKING:  # typing only — never an engine import at runtime (Principle V)
    from speakloop.tts import TTSEngine


def run(
    session: frontmatter.Session,
    *,
    sessions_dir: Path,
    tts_engine: "TTSEngine | None" = None,
    play_fn: Callable[[Path], None] | None = None,
    no_audio: bool = False,
    console: Console | None = None,
    read_key: Callable[[], str] | None = None,
) -> DebriefChoice:
    """Render the debrief for a completed ``session`` and return the next-step choice."""
    console = console or Console()
    key_reader = read_key or menu.read_key

    model = build_view_model(session, sessions_dir=Path(sessions_dir))
    renderer = DebriefRenderer(model, console=console)

    # FR-010: paint the composed view (banner, cards, trend table, transcripts).
    renderer.print_static()

    # US3 (T031) inserts the read-aloud stage here, before the menu.
    _read_aloud(
        model,
        renderer,
        tts_engine=tts_engine,
        play_fn=play_fn,
        no_audio=no_audio,
        console=console,
        read_key=key_reader,
    )

    def _toggle_transcripts() -> None:
        model.transcripts_expanded = not model.transcripts_expanded
        renderer.print_static()

    return menu.run_menu(on_toggle=_toggle_transcripts, console=console, read_key=key_reader)


ANNOUNCEMENT_LINE = "🔊 Reading your feedback aloud — press any key to skip."


def _read_aloud(
    model,
    renderer,
    *,
    tts_engine,
    play_fn,
    no_audio,
    console,
    read_key,
) -> None:
    """Read the educational sections aloud with a moving highlight (US3 / T031).

    Skips entirely when ``no_audio`` is set or no TTS/playback is injected
    (FR-021). Otherwise shows the announcement (FR-016), then reads the ordered
    educational sections (narrative → top priority → patterns, FR-017/FR-018),
    advancing the renderer's highlight + "X of N" progress as each plays
    (FR-019). Any keypress during the announcement or playback skips the rest and
    drops to the menu (FR-020); any TTS/playback error is swallowed by the
    player so the menu still appears (FR-029).
    """
    if no_audio or tts_engine is None or play_fn is None:
        return
    if not model.audio_sections:
        return

    from speakloop.debrief import audio_player
    from speakloop.debrief.renderer import supports_live

    console.print(ANNOUNCEMENT_LINE, style="bold cyan")

    def _run(on_section) -> None:
        with audio_player.KeyboardSkip() as skip:
            audio_player.read_aloud(
                model.audio_sections,
                tts_engine=tts_engine,
                play_fn=play_fn,
                on_section=on_section,
                skip_check=skip.requested,
            )

    if supports_live(console):
        # US3 (FR-019): move the highlight IN PLACE via rich.Live instead of re-emitting the
        # whole composed view per section — print_static stacks a fresh copy of the narrative,
        # banner, table, every grammar card, and transcripts each time and scrolls the terminal.
        # Non-terminals (StringIO test consoles) keep the print_static fallback below, so
        # captured-output assertions stay valid.
        with renderer.live() as live:

            def _on_section(section) -> None:
                progress = f"Reading {section.index} of {model.audio_total} sections"
                live.update(
                    renderer.build(highlight_ref=section.highlight_ref, progress_text=progress),
                    refresh=True,
                )

            _run(_on_section)
    else:

        def _on_section(section) -> None:
            progress = f"Reading {section.index} of {model.audio_total} sections"
            renderer.print_static(highlight_ref=section.highlight_ref, progress_text=progress)

        _run(_on_section)
