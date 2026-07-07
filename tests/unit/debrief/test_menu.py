"""T026 — debrief menu key handling (line-buffered / scripted, no real tty)."""

from __future__ import annotations

import pytest
from rich.console import Console

from speakloop.debrief import menu
from speakloop.debrief.menu import DebriefChoice

pytestmark = pytest.mark.unit

_QUIET = Console(quiet=True)


def _keys(*tokens):
    it = iter(tokens)
    return lambda: next(it)


def _run(*tokens, on_toggle=None):
    return menu.run_menu(read_key=_keys(*tokens), on_toggle=on_toggle, console=_QUIET, show_prompt=False)


def test_r_and_replay_and_enter_are_replay():
    assert _run("r") == DebriefChoice.REPLAY
    assert _run("replay") == DebriefChoice.REPLAY
    assert _run("enter") == DebriefChoice.REPLAY  # Enter on the default


def test_n_and_new_are_new():
    assert _run("n") == DebriefChoice.NEW
    assert _run("new") == DebriefChoice.NEW


def test_q_and_quit_are_quit():
    assert _run("q") == DebriefChoice.QUIT
    assert _run("quit") == DebriefChoice.QUIT


def test_t_toggles_and_keeps_menu_open():
    calls = []
    choice = _run("t", "t", "r", on_toggle=lambda: calls.append(1))
    assert choice == DebriefChoice.REPLAY  # only a terminal choice returns
    assert len(calls) == 2  # toggled twice while the menu stayed open


def test_unknown_key_is_ignored_and_menu_continues():
    assert _run("x", "z", "n") == DebriefChoice.NEW


def test_arrow_navigation_then_enter():
    # REPLAY(0) → down → NEW(1) → Enter.
    assert _run("down", "enter") == DebriefChoice.NEW
    # down twice → QUIT(2).
    assert _run("down", "down", "enter") == DebriefChoice.QUIT
    # up from REPLAY wraps to QUIT(2).
    assert _run("up", "enter") == DebriefChoice.QUIT


def test_parse_line_tokens():
    assert menu._parse_line("") == "enter"
    assert menu._parse_line("  ") == "enter"
    assert menu._parse_line("R") == "r"
    assert menu._parse_line("replay") == "r"
    assert menu._parse_line("NEW") == "n"
    assert menu._parse_line("quit") == "q"
    assert menu._parse_line("t") == "t"


def test_decode_key_arrows_and_specials():
    assert menu._decode_key(b"\x1b[A") == "up"
    assert menu._decode_key(b"\x1b[B") == "down"
    assert menu._decode_key(b"\r") == "enter"
    assert menu._decode_key(b"\n") == "enter"
    assert menu._decode_key(b"\x03") == "quit"  # Ctrl-C
    assert menu._decode_key(b"r") == "r"
    assert menu._decode_key(b"") == "enter"  # EOF on tty → default


def test_eof_on_input_returns_quit(monkeypatch):
    # When stdin isn't a tty and input() raises EOFError, the menu picks QUIT.
    def _raise_eof():
        raise EOFError

    monkeypatch.setattr("builtins.input", lambda *_a, **_k: (_ for _ in ()).throw(EOFError()))
    # Force the line-buffered path: pretend there is no tty. The tty resolution now lives in
    # the shared sessions.keyboard.read_key_blocking, so patch os there (same os singleton).
    from speakloop.sessions import keyboard

    monkeypatch.setattr(keyboard.os, "isatty", lambda _fd: False)
    monkeypatch.setattr(keyboard.os, "open", lambda *_a, **_k: (_ for _ in ()).throw(OSError()))
    assert menu.read_key() == "quit"
