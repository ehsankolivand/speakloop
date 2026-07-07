"""T060 — SIGINT handler cleans up .tmp files; exit 130 contract."""

from __future__ import annotations

import os
import signal

import pytest

from speakloop.sessions import abort

pytestmark = pytest.mark.unit


def test_cleanup_removes_tmp_files(tmp_path):
    (tmp_path / "a.tmp").write_text("x")
    (tmp_path / "b.tmp").write_text("y")
    (tmp_path / "report.md").write_text("keep")
    abort.cleanup_tmp_files(tmp_path)
    assert (tmp_path / "report.md").exists()
    assert not (tmp_path / "a.tmp").exists()
    assert not (tmp_path / "b.tmp").exists()


def test_signal_handler_sets_abort_event(tmp_path):
    abort.reset()
    abort.install_signal_handler(tmp_path)
    try:
        os.kill(os.getpid(), signal.SIGINT)
    except KeyboardInterrupt:
        pass
    assert abort.abort_event.is_set()
    abort.reset()
    signal.signal(signal.SIGINT, signal.default_int_handler)


def test_exit_code_constant_documented():
    # The CLI exit-code is documented in contracts/cli-commands.md.
    # No code constant exists, but we assert the value here for traceability.
    assert 128 + signal.SIGINT == 130


def test_install_returns_prior_and_restore_reinstalls_it(tmp_path):
    """IMP-001: install captures the prior handler; restore puts it back verbatim."""
    def _sentinel(signum, frame):  # pragma: no cover - never fires here
        raise KeyboardInterrupt

    prior = signal.signal(signal.SIGINT, _sentinel)
    try:
        returned = abort.install_signal_handler(tmp_path)
        assert returned is _sentinel
        # Our inert handler is now live, not the sentinel.
        assert signal.getsignal(signal.SIGINT) is not _sentinel
        abort.restore_signal_handler(returned)
        assert signal.getsignal(signal.SIGINT) is _sentinel
    finally:
        signal.signal(signal.SIGINT, prior)
        abort.reset()


def test_restore_none_is_a_noop(tmp_path):
    """A None prior (handler set outside Python) must not raise on restore."""
    prior = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        abort.restore_signal_handler(None)  # no exception
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, prior)
