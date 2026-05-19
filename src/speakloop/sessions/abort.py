"""SIGINT handling: clean up `*.tmp` under sessions_dir, exit 130."""

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


def install_signal_handler(sessions_dir: Path) -> None:
    """Install a SIGINT handler that cleans up tmp files and signals abort.

    The coordinator polls `abort_event` and exits with code 130 (FR-016).
    """

    def _handler(signum, frame):  # noqa: ARG001
        cleanup_tmp_files(sessions_dir)
        abort_event.set()

    signal.signal(signal.SIGINT, _handler)


def reset() -> None:
    """Reset abort state — used by tests."""
    abort_event.clear()
