"""Read the educational debrief sections aloud, synced to the screen (US3).

For each :class:`AudioSection` (narrative → top priority → patterns, FR-018):
synthesize ``speak_text`` through the injected ``TTSEngine`` (its content-
addressed cache is reused automatically, FR-004), advance the on-screen highlight
+ "X of N" progress via the ``on_section`` callback (FR-019), then play it with
the injected ``play_fn``. Any keypress stops the *remaining* audio and returns so
the menu appears immediately (FR-020); any TTS/playback error is swallowed for
the same reason (FR-029).

Principle V: NO engine-specific imports. TTS is used only via the injected
``TTSEngine``; playback only via the injected ``play_fn``. Skip detection uses
the standard-library tty reader (``termios``/``select``), never an audio package,
so this module imports nothing engine-specific.
"""

from __future__ import annotations

import os
import select
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from speakloop.debrief.view_model import AudioSection


@dataclass(frozen=True)
class AudioOutcome:
    played: int  # how many sections actually played
    skipped: bool  # the user pressed a key
    errored: bool  # TTS/playback raised; we returned so the menu still appears


class KeyboardSkip:
    """Background any-key listener used to skip the read-aloud (FR-020).

    Spans the announcement + playback. Uses the project's two-tier tty strategy
    (stdin if it's a tty, else ``/dev/tty``); if neither is available (piped
    input, no controlling terminal) it simply never reports a skip.
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fd: int | None = None
        self._own_fd = False

    def requested(self) -> bool:
        return self._event.is_set()

    def __enter__(self) -> KeyboardSkip:
        fd: int | None = None
        try:
            candidate = sys.stdin.fileno()
            if os.isatty(candidate):
                fd = candidate
        except (OSError, ValueError):
            fd = None
        if fd is None:
            try:
                fd = os.open("/dev/tty", os.O_RDONLY)
                self._own_fd = True
            except OSError:
                return self  # no terminal → skip is simply never reported
        self._fd = fd
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        import termios
        import tty

        fd = self._fd
        assert fd is not None
        try:
            saved = termios.tcgetattr(fd)
        except termios.error:
            saved = None
        try:
            if saved is not None:
                tty.setcbreak(fd, termios.TCSANOW)
            while not self._stop.is_set():
                try:
                    ready, _, _ = select.select([fd], [], [], 0.1)
                except (OSError, ValueError):
                    return
                if not ready:
                    continue
                try:
                    data = os.read(fd, 1)
                except OSError:
                    return
                if data:
                    self._event.set()
                    return
        finally:
            if saved is not None:
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, saved)
                except termios.error:
                    pass

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._own_fd and self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass


def read_aloud(
    sections: Sequence[AudioSection],
    *,
    tts_engine,
    play_fn: Callable[[Path], None],
    on_section: Callable[[AudioSection], None] | None = None,
    skip_check: Callable[[], bool] | None = None,
) -> AudioOutcome:
    """Play the educational ``sections`` in order; return when done/skipped/errored.

    ``on_section`` is invoked for each section before it plays so the renderer can
    move the highlight and update the "X of N" progress line. ``skip_check`` is
    polled before each section (and after each clip); when it returns True the
    remaining audio is abandoned and control returns to the caller (the menu).
    """
    on_section = on_section or (lambda _s: None)
    skip_check = skip_check or (lambda: False)

    played = 0
    for section in sections:
        if skip_check():
            return AudioOutcome(played=played, skipped=True, errored=False)
        # Highlight first so the active section shows while it synthesises/plays.
        on_section(section)
        try:
            wav = tts_engine.synthesize(section.speak_text)
        except Exception:  # noqa: BLE001 — never hang the debrief on TTS failure (FR-029)
            return AudioOutcome(played=played, skipped=False, errored=True)
        try:
            play_fn(Path(wav))
        except Exception:  # noqa: BLE001 — playback failure must still reach the menu (FR-029)
            return AudioOutcome(played=played, skipped=False, errored=True)
        played += 1
        if skip_check():
            return AudioOutcome(played=played, skipped=True, errored=False)
    return AudioOutcome(played=played, skipped=False, errored=False)
