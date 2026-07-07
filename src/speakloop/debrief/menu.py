"""Debrief menu: r/n/q (+ replay/new/quit), default REPLAY, arrow nav, `t` toggle.

Reuses the project's proven two-tier tty pattern (research.md §f): a raw
single-byte/escape-sequence read via ``termios``/``tty.setcbreak`` (stdin, then a
``/dev/tty`` fallback), with a line-buffered ``input()`` fallback for piped/
scripted use so the menu is testable without a real terminal.

The transcript-toggle key ``t`` is NOT a terminal choice (contract / data-model
§C.6): it flips ``transcripts_expanded`` via the injected ``on_toggle`` callback,
re-renders in place, and keeps the menu open. Only replay/new/quit returns.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from enum import Enum

from rich.console import Console

from speakloop.sessions import keyboard


class DebriefChoice(str, Enum):
    """The user's terminal menu selection (FR-023/FR-024)."""

    REPLAY = "replay"  # r / replay — same question, fresh 4/3/2, no model reload
    NEW = "new"  # n / new       — open the question picker
    QUIT = "quit"  # q / quit     — return to the shell


_ORDER = (DebriefChoice.REPLAY, DebriefChoice.NEW, DebriefChoice.QUIT)


def _decode_key(data: bytes) -> str:
    if not data:
        return "enter"  # EOF on the tty → treat as the default
    if data == b"\x1b[A":
        return "up"
    if data == b"\x1b[B":
        return "down"
    b0 = data[:1]
    if b0 in (b"\r", b"\n"):
        return "enter"
    if b0 == b"\x03":  # Ctrl-C
        return "quit"
    try:
        ch = b0.decode("utf-8").lower()
    except UnicodeDecodeError:
        return ""
    return ch


def _parse_line(line: str) -> str:
    """Map a typed line to a canonical token (line-buffered / piped fallback)."""
    stripped = line.strip().lower()
    if not stripped:
        return "enter"
    if stripped in ("r", "replay"):
        return "r"
    if stripped in ("n", "new"):
        return "n"
    if stripped in ("q", "quit"):
        return "q"
    if stripped in ("t", "toggle"):
        return "t"
    return stripped[:1]


def read_key() -> str:
    """Canonical key token: up/down/enter/r/n/q/t/quit, or a single char.

    Two-tier (raw cbreak on stdin then /dev/tty — 3 bytes for arrow escapes — else
    line-buffered input) via the shared ``sessions.keyboard.read_key_blocking``; EOF on the
    input stream → ``quit`` (the safest terminal choice). ``_decode_key``/``_parse_line`` keep
    this menu's token table distinct from the listen loop's case-sensitive r/R table.
    """
    return keyboard.read_key_blocking(
        decode=_decode_key, line_parse=_parse_line, read_bytes=3, eof_value="quit"
    )


def _prompt(console: Console, selection: int) -> None:
    parts = []
    labels = {DebriefChoice.REPLAY: "(r) replay", DebriefChoice.NEW: "(n) new", DebriefChoice.QUIT: "(q) quit"}
    for i, choice in enumerate(_ORDER):
        label = labels[choice]
        parts.append(f"[reverse]{label}[/reverse]" if i == selection else label)
    console.print(
        "\n" + "   ".join(parts) + "   [dim](t toggles transcripts · ↑/↓ then Enter)[/dim]"
    )


def run_menu(
    *,
    on_toggle: Callable[[], None] | None = None,
    console: Console | None = None,
    read_key: Callable[[], str] = read_key,
    show_prompt: bool = True,
) -> DebriefChoice:
    """Loop reading keys until a terminal choice (replay/new/quit) is made.

    ``t`` invokes ``on_toggle`` (flip transcript expansion + re-render) and keeps
    the menu open. Arrow keys move the selection; Enter selects it (default
    REPLAY). Direct keys r/n/q (and the full words) jump straight to a choice.
    """
    console = console or Console()
    selection = 0  # REPLAY is the default
    while True:
        if show_prompt:
            _prompt(console, selection)
            sys.stdout.flush()
        key = read_key()
        if key in ("r", "replay"):
            return DebriefChoice.REPLAY
        if key in ("n", "new"):
            return DebriefChoice.NEW
        if key in ("q", "quit"):
            return DebriefChoice.QUIT
        if key == "enter":
            return _ORDER[selection]
        if key == "up":
            selection = (selection - 1) % len(_ORDER)
            continue
        if key == "down":
            selection = (selection + 1) % len(_ORDER)
            continue
        if key == "t":
            if on_toggle is not None:
                on_toggle()
            continue
        # Unknown key → ignore and re-prompt.
