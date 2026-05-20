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

import os
import sys
from collections.abc import Callable
from enum import Enum

from rich.console import Console


class DebriefChoice(str, Enum):
    """The user's terminal menu selection (FR-023/FR-024)."""

    REPLAY = "replay"  # r / replay — same question, fresh 4/3/2, no model reload
    NEW = "new"  # n / new       — open the question picker
    QUIT = "quit"  # q / quit     — return to the shell


_ORDER = (DebriefChoice.REPLAY, DebriefChoice.NEW, DebriefChoice.QUIT)


def _cbreak_read_key(fd: int) -> str | None:
    """Read one key (or arrow escape sequence) in cbreak mode. None on failure."""
    import termios
    import tty

    try:
        saved = termios.tcgetattr(fd)
    except termios.error:
        return None
    try:
        tty.setcbreak(fd, termios.TCSANOW)
        try:
            data = os.read(fd, 3)  # 1 byte for a normal key; 3 for an arrow (\x1b[A/B)
        except OSError:
            return None
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        except termios.error:
            pass
    return _decode_key(data)


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

    Two-tier: raw tty read (stdin, then /dev/tty), else line-buffered input.
    """
    fd: int | None = None
    try:
        fd = sys.stdin.fileno()
    except (OSError, ValueError):
        fd = None
    if fd is not None and os.isatty(fd):
        key = _cbreak_read_key(fd)
        if key is not None:
            return key

    tty_fd: int | None = None
    try:
        tty_fd = os.open("/dev/tty", os.O_RDONLY)
    except OSError:
        tty_fd = None
    if tty_fd is not None:
        try:
            key = _cbreak_read_key(tty_fd)
        finally:
            try:
                os.close(tty_fd)
            except OSError:
                pass
        if key is not None:
            return key

    try:
        return _parse_line(input())
    except EOFError:
        return "quit"  # no input stream left → safest terminal choice


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
