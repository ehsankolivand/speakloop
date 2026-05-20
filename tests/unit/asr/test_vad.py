"""T020 — VAD segmentation: tunables, merge logic, all-silence → [] (FR-005).

Silero is stubbed (no torch/onnx model load). We test the pure merge step
directly and the param plumbing of `segment()` via a fake silero_vad module.
"""

from __future__ import annotations

import sys
import types

import pytest

from speakloop.asr import vad

pytestmark = pytest.mark.unit


def test_vad_settings_reports_research_thresholds():
    s = vad.vad_settings()
    assert s == {
        "engine": "silero",
        "speech_threshold": 0.5,
        "min_speech_ms": 250,
        "min_silence_ms": 100,
        "merge_gap_ms": 300,
        "speech_pad_ms": 30,
    }


def test_merge_combines_regions_within_gap():
    regions = [
        vad.SpeechRegion(0.0, 1.0),
        vad.SpeechRegion(1.2, 2.0),  # 200 ms gap -> merge
        vad.SpeechRegion(5.0, 6.0),  # 3 s gap -> keep separate
    ]
    merged = vad._merge(regions, gap_seconds=0.3)
    assert merged == [vad.SpeechRegion(0.0, 2.0), vad.SpeechRegion(5.0, 6.0)]


def test_merge_keeps_regions_beyond_gap():
    regions = [vad.SpeechRegion(0.0, 1.0), vad.SpeechRegion(1.5, 2.0)]  # 500 ms gap
    assert vad._merge(regions, gap_seconds=0.3) == regions


def test_merge_empty_is_empty():
    assert vad._merge([], gap_seconds=0.3) == []


def _install_fake_silero(monkeypatch, timestamps, captured):
    fake = types.ModuleType("silero_vad")
    fake.read_audio = lambda path, sampling_rate=16000: ("AUDIO", sampling_rate)
    fake.load_silero_vad = lambda onnx=False: "MODEL"

    def _gst(audio, model, **kwargs):
        captured.update(kwargs)
        captured["audio"] = audio
        captured["model"] = model
        return timestamps

    fake.get_speech_timestamps = _gst
    monkeypatch.setitem(sys.modules, "silero_vad", fake)


def test_segment_passes_tunables_and_merges(monkeypatch, tmp_path):
    captured: dict = {}
    # Two regions 200 ms apart -> should merge to one.
    _install_fake_silero(
        monkeypatch,
        [{"start": 0.0, "end": 1.0}, {"start": 1.2, "end": 2.0}],
        captured,
    )
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"\x00")

    regions = vad.segment(wav)

    assert captured["threshold"] == 0.5
    assert captured["min_speech_duration_ms"] == 250
    assert captured["min_silence_duration_ms"] == 100
    assert captured["speech_pad_ms"] == 30
    assert captured["sampling_rate"] == 16000
    assert captured["return_seconds"] is True
    assert regions == [vad.SpeechRegion(0.0, 2.0)]


def test_segment_all_silence_returns_empty(monkeypatch, tmp_path):
    _install_fake_silero(monkeypatch, [], {})
    wav = tmp_path / "silent.wav"
    wav.write_bytes(b"\x00")
    assert vad.segment(wav) == []
