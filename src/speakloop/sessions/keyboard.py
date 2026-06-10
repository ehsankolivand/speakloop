"""Injectable single-key reader (012-responsive-session-flow, US1).

The ONE raw-input module — consolidates the cbreak logic previously duplicated in
``cli/practice._cbreak_read`` and ``coordinator._spawn_enter_reader``. Every session
control (skip / replay / early-stop / skip-follow-up) polls a ``KeyReader``; tests
inject ``FakeKeyReader`` so no automated test ever touches a real keyboard.

Canonical keys returned by ``poll()`` (or ``None`` when no key is waiting):

  "space"  ← 0x20            "enter"  ← \\r / \\n (alias of space at call sites)
  "r"/"R"  ← letter verbatim  "s"/"q" ← letter verbatim
  "q"      ← Ctrl-C (0x03) where quitting exists

Raw mode uses only the standard library (termios/tty/select). When no tty is reachable
(piped stdin, no controlling terminal — measured failure mode), the factory returns a
``NullKeyReader`` and the session falls back to the line/timeout path (FR-012).
"""

from __future__ import annotations

import contextlib
import os
import select
import sys
from collections.abc import Callable
from typing import Protocol, runtime_checkable


def canonicalize(data: bytes) -> str | None:
    """Map a raw 1-byte read to a canonical key name, or None if it has no meaning."""
    if not data:
        return None
    if data in (b" ",):
        return "space"
    if data in (b"\r", b"\n"):
        return "enter"
    if data == b"\x03":  # Ctrl-C
        return "q"
    try:
        ch = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if ch.isprintable() and len(ch) == 1:
        return ch
    return None


@runtime_checkable
class KeyReader(Protocol):
    """Non-blocking single-key reader. A context manager owns raw-mode setup/teardown."""

    raw_capable: bool

    def __enter__(self) -> KeyReader: ...
    def __exit__(self, *exc) -> None: ...
    def poll(self) -> str | None:
        """Return the next pending canonical key, or None if none is waiting."""
        ...


class NullKeyReader:
    """Fallback reader for terminals without raw-mode support: never yields a key.

    The session still completes via the existing line-based path + time budgets (FR-012).
    """

    raw_capable = False

    def __enter__(self) -> NullKeyReader:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def poll(self) -> str | None:
        return None


class RawKeyReader:
    """termios/tty cbreak reader over a resolved tty fd (stdin, else ``/dev/tty``)."""

    raw_capable = True

    def __init__(self) -> None:
        self._fd: int | None = None
        self._own_fd = False
        self._saved = None
        self._depth = 0  # re-entrancy guard: this object is deliberately shared + re-entered

    def _resolve_fd(self) -> int | None:
        try:
            candidate = sys.stdin.fileno()
            if os.isatty(candidate):
                return candidate
        except (OSError, ValueError):
            pass
        try:
            fd = os.open("/dev/tty", os.O_RDONLY)
        except OSError:
            return None
        self._own_fd = True
        return fd

    def __enter__(self) -> RawKeyReader:
        import termios
        import tty

        # Re-entrancy guard: a nested/repeated `with` on this (deliberately shared) reader
        # must NOT re-`tcgetattr` (that would save the already-cbreak attrs and leave the
        # terminal stuck in cbreak) nor re-open `/dev/tty` (an fd leak). Only the outermost
        # enter acquires; only the outermost exit restores.
        self._depth += 1
        if self._depth > 1:
            return self

        fd = self._resolve_fd()
        if fd is None:
            # No tty reachable — behave like a NullKeyReader for this session.
            self._fd = None
            return self
        try:
            self._saved = termios.tcgetattr(fd)
            tty.setcbreak(fd, termios.TCSANOW)
            # Drain anything typed before this stage so we don't trip a control at t=0.
            termios.tcflush(fd, termios.TCIFLUSH)
            self._fd = fd
        except termios.error:
            # Could not enter raw mode — degrade to no-op.
            if self._own_fd:
                with contextlib.suppress(OSError):
                    os.close(fd)
            self._fd = None
            self._own_fd = False
        return self

    def __exit__(self, *exc) -> None:
        import termios

        self._depth = max(0, self._depth - 1)
        if self._depth > 0:
            return  # inner exit of a nested `with` — keep raw mode until the outermost exit
        if self._fd is not None and self._saved is not None:
            with contextlib.suppress(termios.error):
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        if self._own_fd and self._fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._fd)
        self._fd = None
        self._own_fd = False
        self._saved = None

    def poll(self) -> str | None:
        if self._fd is None:
            return None
        try:
            ready, _, _ = select.select([self._fd], [], [], 0)
        except (OSError, ValueError):
            return None
        if not ready:
            return None
        try:
            data = os.read(self._fd, 1)
        except OSError:
            return None
        return canonicalize(data)


class FakeKeyReader:
    """Test double. Returns scripted keys without ever opening a real fd.

    Two modes (compose freely):
      * ``FakeKeyReader(["space", None, "r"])`` — one item per ``poll()`` call.
      * ``FakeKeyReader(schedule=[(0.2, "space")], clock=fake_clock)`` — time-gated:
        ``poll()`` returns a key once its due time has elapsed since ``__enter__``.
    """

    raw_capable = True

    def __init__(
        self,
        keys: list[str | None] | None = None,
        *,
        schedule: list[tuple[float, str]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._queue: list[str | None] = list(keys or [])
        self._schedule: list[tuple[float, str]] = list(schedule or [])
        self._clock = clock
        self.entered = False
        self._start = 0.0

    def __enter__(self) -> FakeKeyReader:
        self.entered = True
        self._start = self._clock() if self._clock is not None else 0.0
        return self

    def __exit__(self, *exc) -> None:
        self.entered = False

    def poll(self) -> str | None:
        if self._schedule and self._clock is not None:
            now = self._clock() - self._start
            for i, (due, key) in enumerate(self._schedule):
                if due <= now:
                    self._schedule.pop(i)
                    return key
            return None
        if self._queue:
            return self._queue.pop(0)
        return None


def make_key_reader() -> KeyReader:
    """Return a ``RawKeyReader`` if a tty is reachable, else a ``NullKeyReader`` (FR-012)."""
    try:
        if os.isatty(sys.stdin.fileno()):
            return RawKeyReader()
    except (OSError, ValueError):
        pass
    # stdin is not a tty; a controlling terminal may still exist.
    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
        os.close(fd)
        return RawKeyReader()
    except OSError:
        return NullKeyReader()
