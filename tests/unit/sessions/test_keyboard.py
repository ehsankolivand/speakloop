"""T007 — KeyReader: canonicalization, FakeKeyReader, NullKeyReader. No real fd."""

from __future__ import annotations

import pytest

from speakloop.sessions import keyboard

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b" ", "space"),
        (b"\r", "enter"),
        (b"\n", "enter"),
        (b"\x03", "q"),  # Ctrl-C
        (b"r", "r"),
        (b"R", "R"),  # case preserved (listen-loop distinguishes r/R)
        (b"s", "s"),
        (b"q", "q"),
        (b"", None),  # EOF
        (b"\x1b", None),  # non-printable escape → ignored
    ],
)
def test_canonicalize(raw, expected):
    assert keyboard.canonicalize(raw) == expected


def test_null_key_reader_never_yields():
    r = keyboard.NullKeyReader()
    assert r.raw_capable is False
    with r as ctx:
        assert ctx.poll() is None
        assert ctx.poll() is None


def test_fake_key_reader_queue_mode():
    r = keyboard.FakeKeyReader(["space", None, "r"])
    with r:
        assert r.poll() == "space"
        assert r.poll() is None
        assert r.poll() == "r"
        assert r.poll() is None  # exhausted → None forever


def test_fake_key_reader_schedule_mode():
    clock = {"t": 0.0}
    r = keyboard.FakeKeyReader(schedule=[(0.5, "space")], clock=lambda: clock["t"])
    with r:
        assert r.poll() is None  # not due yet
        clock["t"] = 0.6
        assert r.poll() == "space"
        assert r.poll() is None  # consumed


def test_fake_key_reader_is_a_keyreader():
    assert isinstance(keyboard.FakeKeyReader(), keyboard.KeyReader)
    assert isinstance(keyboard.NullKeyReader(), keyboard.KeyReader)


def test_read_key_blocking_line_buffered_fallback(monkeypatch):
    """IMP-016: with no tty, the shared reader falls to line_parse(input()) — decode is
    never called (that path needs a real tty)."""
    monkeypatch.setattr(keyboard.os, "isatty", lambda _fd: False)
    monkeypatch.setattr(keyboard.os, "open", lambda *_a, **_k: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "REPLAY")

    def _decode(_b):
        raise AssertionError("decode must not run on the line-buffered path")

    got = keyboard.read_key_blocking(
        decode=_decode, line_parse=lambda s: f"parsed:{s.lower()}", read_bytes=1, eof_value="EOF",
    )
    assert got == "parsed:replay"


def test_read_key_blocking_eof_returns_eof_value(monkeypatch):
    monkeypatch.setattr(keyboard.os, "isatty", lambda _fd: False)
    monkeypatch.setattr(keyboard.os, "open", lambda *_a, **_k: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: (_ for _ in ()).throw(EOFError()))
    got = keyboard.read_key_blocking(
        decode=lambda _b: "x", line_parse=lambda s: s, read_bytes=3, eof_value="quit",
    )
    assert got == "quit"
