"""T011 — play_interruptible control loop, with sounddevice fully stubbed (no real audio)."""

from __future__ import annotations

import pytest

from speakloop.audio import playback

pytestmark = pytest.mark.unit


class _FakeStream:
    def __init__(self, frames_until_done: int) -> None:
        self._left = frames_until_done

    @property
    def active(self) -> bool:
        # Each poll consumes one "frame"; goes inactive when drained.
        if self._left <= 0:
            return False
        self._left -= 1
        return True


@pytest.fixture
def _stub_sd(monkeypatch):
    state = {"play": 0, "stop": 0, "wait": 0, "stream": None}

    def fake_play(data, samplerate):
        state["play"] += 1

    def fake_stop(ignore_errors=False):
        state["stop"] += 1

    def fake_wait():
        state["wait"] += 1

    def fake_get_stream():
        return state["stream"]

    monkeypatch.setattr("sounddevice.play", fake_play)
    monkeypatch.setattr("sounddevice.stop", fake_stop)
    monkeypatch.setattr("sounddevice.wait", fake_wait)
    monkeypatch.setattr("sounddevice.get_stream", fake_get_stream)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    return state


def test_runs_to_completion_when_never_stopped(_stub_sd, wav_fixture):
    _stub_sd["stream"] = _FakeStream(frames_until_done=3)
    interrupted = playback.play_interruptible(
        wav_fixture("test-clip.wav"), should_stop=lambda: False
    )
    assert interrupted is False
    assert _stub_sd["play"] == 1
    assert _stub_sd["stop"] == 0  # ran to the end, never aborted
    assert _stub_sd["wait"] == 1  # drained the tail


def test_stops_promptly_when_should_stop_flips(_stub_sd, wav_fixture):
    _stub_sd["stream"] = _FakeStream(frames_until_done=1000)  # would play "forever"
    polls = {"n": 0}

    def should_stop():
        polls["n"] += 1
        return polls["n"] >= 2  # stop on the second poll

    interrupted = playback.play_interruptible(
        wav_fixture("test-clip.wav"), should_stop=should_stop
    )
    assert interrupted is True
    assert _stub_sd["stop"] == 1
    assert _stub_sd["wait"] == 0  # interrupted, not drained


def test_on_first_frame_callback_fires(_stub_sd, wav_fixture):
    _stub_sd["stream"] = _FakeStream(frames_until_done=1)
    fired = []
    playback.play_interruptible(
        wav_fixture("test-clip.wav"),
        should_stop=lambda: False,
        on_first_frame=lambda: fired.append(True),
    )
    assert fired == [True]


def test_missing_wav_raises(_stub_sd, tmp_path):
    from pathlib import Path

    with pytest.raises(playback.PlaybackError):
        playback.play_interruptible(Path(tmp_path) / "missing.wav", should_stop=lambda: False)


def test_warm_output_device_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no device")

    monkeypatch.setattr("sounddevice.play", boom)
    monkeypatch.setattr("sounddevice.stop", lambda **k: None)
    # Must not raise — warm-up is best-effort.
    playback.warm_output_device()
