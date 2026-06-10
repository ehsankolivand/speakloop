"""T041 — playback delegates to sounddevice without actually playing audio."""

from __future__ import annotations

import sounddevice as sd
import soundfile as sf
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


@pytest.fixture
def _silence_retry(monkeypatch):
    """Make the retry path instant and offline: no real PortAudio reload or sleep."""
    monkeypatch.setattr("sounddevice.wait", lambda: None)
    monkeypatch.setattr("sounddevice.stop", lambda ignore_errors=True: None)
    monkeypatch.setattr(playback, "_reinitialize", lambda: None)
    monkeypatch.setattr(playback.time, "sleep", lambda *a, **k: None)


def test_transient_portaudio_error_is_retried_after_reload(
    monkeypatch, wav_fixture, _silence_retry
):
    """A first-open failure (the headphones-powered-off case) reloads PortAudio
    and retries; the second open succeeds and playback completes."""
    plays = {"n": 0}
    reloads = {"n": 0}

    def fake_play(data, samplerate):
        plays["n"] += 1
        if plays["n"] == 1:
            raise sd.PortAudioError("Internal PortAudio error [PaErrorCode -9986]")

    monkeypatch.setattr("sounddevice.play", fake_play)
    monkeypatch.setattr(playback, "_reinitialize", lambda: reloads.__setitem__("n", reloads["n"] + 1))

    playback.play(wav_fixture("test-clip.wav"))  # no exception
    assert plays["n"] == 2  # failed once, retried once
    assert reloads["n"] == 1  # PortAudio reloaded before the retry


def test_falls_back_to_device_native_rate(monkeypatch, wav_fixture, _silence_retry):
    """When the clip's own rate keeps failing, the clip is resampled to the
    device's native rate and played there."""
    clip_rate = sf.info(str(wav_fixture("test-clip.wav"))).samplerate
    device_rate = clip_rate * 2  # guaranteed different from the clip rate
    played_rates = []

    def fake_play(data, samplerate):
        played_rates.append(samplerate)
        if samplerate != device_rate:  # the clip-rate opens all fail
            raise sd.PortAudioError("Audio Unit: Invalid Property Value [-10851]")

    monkeypatch.setattr("sounddevice.play", fake_play)
    monkeypatch.setattr(playback, "_device_output_rate", lambda: device_rate)
    monkeypatch.setattr(playback, "_resample", lambda data, s, d: data)

    playback.play(wav_fixture("test-clip.wav"))  # succeeds via the fallback
    assert played_rates[-1] == device_rate  # last (successful) open was at device rate
    assert any(r != device_rate for r in played_rates)  # clip-rate opens were tried first


def test_persistent_failure_raises_playback_error(monkeypatch, wav_fixture, _silence_retry):
    """If every open fails, the original PortAudio error is surfaced as a
    PlaybackError after the retries and the native-rate fallback are exhausted."""
    plays = {"n": 0}

    def always_fail(data, samplerate):
        plays["n"] += 1
        raise sd.PortAudioError("Internal PortAudio error [PaErrorCode -9986]")

    monkeypatch.setattr("sounddevice.play", always_fail)
    monkeypatch.setattr(playback, "_device_output_rate", lambda: 0)  # no fallback rate

    with pytest.raises(playback.PlaybackError):
        playback.play(wav_fixture("test-clip.wav"))
    assert plays["n"] == playback._OPEN_RETRIES  # exhausted every retry
