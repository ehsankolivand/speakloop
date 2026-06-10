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
