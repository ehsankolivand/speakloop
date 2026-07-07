"""SIGINT handling: clean up `*.tmp` under sessions_dir and signal abort.

The handler itself never exits; it sets `abort_event`, which the coordinator
polls and turns into an `AbortedError`. `cli/practice.py` catches that and exits
130 (FR-016). The handler is installed for the duration of `run_session` only and
the previous handler is restored on the way out (see `restore_signal_handler`).
"""

from __future__ import annotations

import signal
import threading
from pathlib import Path

abort_event = threading.Event()


def cleanup_tmp_files(sessions_dir: Path) -> int:
    """Remove every `*.tmp` under `sessions_dir`. Returns count removed."""
    if not sessions_dir.exists():
        return 0
    n = 0
    for p in sessions_dir.rglob("*.tmp"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n


def install_signal_handler(sessions_dir: Path):
    """Install a SIGINT handler that cleans up tmp files and signals abort.

    The coordinator polls `abort_event` and raises AbortedError; the CLI
    (`cli/practice.py`) catches it and exits with code 130 (FR-016).

    Returns the previously-installed SIGINT handler so the caller can restore it
    via `restore_signal_handler` once the session is over — otherwise this inert
    handler stays live for the rest of the process and silently swallows every
    later Ctrl-C (it never raises). Must run on the main thread.
    """
    previous = signal.getsignal(signal.SIGINT)

    def _handler(signum, frame):  # noqa: ARG001
        cleanup_tmp_files(sessions_dir)
        abort_event.set()

    signal.signal(signal.SIGINT, _handler)
    return previous


def restore_signal_handler(previous) -> None:
    """Reinstall the SIGINT handler captured by `install_signal_handler`.

    `previous` may be a callable, `signal.SIG_DFL`, or `signal.SIG_IGN`. A `None`
    means the prior handler was not installed from Python (rare); leave it alone
    rather than raising. Must run on the main thread (`signal.signal` requirement).
    """
    if previous is not None:
        signal.signal(signal.SIGINT, previous)


def reset() -> None:
    """Reset abort state — used by tests."""
    abort_event.clear()
