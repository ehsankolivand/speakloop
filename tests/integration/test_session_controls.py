"""T021/T022 — single-key control paths + edge cases, driven by FakeKeyReader.

No real microphone, speaker, or keyboard: recording is a fake that honors the
early-exit event; playback is a stubbed interruptible player. Verifies skip / replay /
early-stop / skip-follow-up and the FR-011/FR-012 edge cases.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

import pytest
from rich.console import Console

from speakloop.cli import practice
from speakloop.sessions import coordinator
from speakloop.sessions.keyboard import FakeKeyReader, NullKeyReader

pytestmark = pytest.mark.integration

_NOOP_SLEEP = lambda *_: None  # noqa: E731 — tiny test helper


def _console() -> Console:
    return Console(file=io.StringIO(), width=100)


def _record_fn_respecting_early(duration=0.4):
    """A fake recorder that stops the moment early_exit_event is set (or a short budget)."""

    def record(out_path, time_budget_seconds, early_exit_event):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00")
        deadline = time.monotonic() + min(time_budget_seconds, duration)
        while time.monotonic() < deadline:
            if early_exit_event.is_set():
                break
            time.sleep(0.005)
        return 0.3

    return record


# --- recording controls ------------------------------------------------------


def test_space_ends_recording_early(tmp_path):
    early = threading.Event()
    key = FakeKeyReader(["space"])  # raw_capable True → poller active
    started = time.monotonic()
    _, skipped = coordinator._record_stage(
        record_fn=_record_fn_respecting_early(duration=10.0),  # would run "forever"
        wav_path=tmp_path / "a.wav",
        budget=240,
        label="attempt 1",
        key_reader=key,
        ui_sleep=_NOOP_SLEEP,
        console=_console(),
        early_exit_event=early,
    )
    assert early.is_set()  # the key poller stopped it
    assert skipped is False
    assert time.monotonic() - started < 2.0  # ended promptly, not after the 10s budget


def test_s_skips_a_follow_up_recording(tmp_path):
    early = threading.Event()
    key = FakeKeyReader(["s"])
    _, skipped = coordinator._record_stage(
        record_fn=_record_fn_respecting_early(duration=10.0),
        wav_path=tmp_path / "f.wav",
        budget=60,
        label="follow-up 1",
        key_reader=key,
        ui_sleep=_NOOP_SLEEP,
        console=_console(),
        early_exit_event=early,
        follow_up=True,
    )
    assert skipped is True
    assert early.is_set()


def test_unbound_key_during_recording_is_ignored(tmp_path):
    """FR-011: a key with no binding in this state is ignored — no crash, no early stop."""
    early = threading.Event()
    key = FakeKeyReader(["q", "x", "z"])  # none of these stop a recording
    _, skipped = coordinator._record_stage(
        record_fn=_record_fn_respecting_early(duration=0.2),
        wav_path=tmp_path / "a.wav",
        budget=0.2,
        label="attempt 1",
        key_reader=key,
        ui_sleep=_NOOP_SLEEP,
        console=_console(),
        early_exit_event=early,
    )
    assert early.is_set() is False  # ran to its (short) budget, never tripped
    assert skipped is False


def test_null_key_reader_recording_completes(tmp_path):
    """FR-012: no tty → no poller/countdown; the recording still runs to budget."""
    early = threading.Event()
    duration, skipped = coordinator._record_stage(
        record_fn=_record_fn_respecting_early(duration=0.1),
        wav_path=tmp_path / "a.wav",
        budget=0.1,
        label="attempt 1",
        key_reader=NullKeyReader(),
        ui_sleep=_NOOP_SLEEP,
        console=_console(),
        early_exit_event=early,
    )
    assert duration == 0.3
    assert skipped is False


# --- listen-loop clip controls ----------------------------------------------


def _stub_interruptible(monkeypatch, polls_until_stop=1):
    """Stub playback.play_interruptible to poll should_stop a few times (no real audio)."""

    def fake_pi(wav, *, should_stop, on_first_frame=None, poll_interval=0.0):
        for _ in range(50):
            if should_stop():
                return True
        return False

    monkeypatch.setattr("speakloop.audio.playback.play_interruptible", fake_pi)


def test_listen_clip_replay_on_r(monkeypatch, tmp_path):
    _stub_interruptible(monkeypatch)
    wav = tmp_path / "q.wav"
    wav.write_bytes(b"\x00")
    key = FakeKeyReader(["r"])
    result = practice._play_listen_clip(_console(), "question", wav, key_reader=key, play_fn=lambda w: None)
    assert result == "replay"


def test_listen_clip_skip_on_space(monkeypatch, tmp_path):
    _stub_interruptible(monkeypatch)
    wav = tmp_path / "q.wav"
    wav.write_bytes(b"\x00")
    key = FakeKeyReader(["space"])
    result = practice._play_listen_clip(_console(), "question", wav, key_reader=key, play_fn=lambda w: None)
    assert result == "done"


def test_listen_clip_non_interactive_uses_play_fn(tmp_path):
    """NullKeyReader → blocking play_fn path (today's behavior), returns 'done'."""
    wav = tmp_path / "q.wav"
    wav.write_bytes(b"\x00")
    played = []
    result = practice._play_listen_clip(
        _console(), "question", wav, key_reader=NullKeyReader(), play_fn=lambda w: played.append(w)
    )
    assert result == "done"
    assert played == [wav]


# --- follow-up prompt skip ---------------------------------------------------


def test_play_prompt_skip_followup_on_s(monkeypatch, tmp_path):
    _stub_interruptible(monkeypatch)
    wav = tmp_path / "p.wav"
    wav.write_bytes(b"\x00")
    key = FakeKeyReader(["s"])

    def synth(text, voice=None):
        return wav

    result = coordinator._play_prompt(
        synth, "follow-up?", None, key_reader=key, play_fn=lambda w: None,
        console=_console(), follow_up=True,
    )
    assert result == "skip_followup"
