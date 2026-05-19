"""T041 — playback delegates to sounddevice without actually playing audio."""

from __future__ import annotations

import pytest

from speakloop.audio import playback

pytestmark = pytest.mark.unit


def test_play_calls_sounddevice_with_wav_data(monkeypatch, wav_fixture):
    calls = []

    def fake_play(data, samplerate):
        calls.append(("play", data.shape, samplerate))

    def fake_wait():
        calls.append(("wait",))

    monkeypatch.setattr("sounddevice.play", fake_play)
    monkeypatch.setattr("sounddevice.wait", fake_wait)

    playback.play(wav_fixture("test-clip.wav"))
    assert calls[0][0] == "play"
    assert calls[1] == ("wait",)


def test_missing_wav_raises(tmp_path):
    from pathlib import Path

    with pytest.raises(playback.PlaybackError):
        playback.play(Path(tmp_path) / "does-not-exist.wav")
