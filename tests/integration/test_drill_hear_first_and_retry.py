"""T011 (017) — the interview drill block hears the target first and retries a flagged item.

Exercises the real `_record_stage` UI + the TTS `speak` closure + `run_drill_item` wiring via
`coordinator._run_pronunciation_drills`, with a fake recorder/scorer/TTS and an interactive
`FakeKeyReader`. No real model / mic / tty / network.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from speakloop.pronunciation import load_drill_bank
from speakloop.pronunciation.interface import DrillResult, PhoneFlag
from speakloop.sessions import abort, coordinator
from speakloop.sessions.keyboard import FakeKeyReader

pytestmark = pytest.mark.integration


class _FakeTTS:
    def __init__(self, events, tmp):
        self.events = events
        self._tmp = tmp

    def synthesize(self, text, voice=None):
        self.events.append(("synth", text))
        p = self._tmp / "tts.wav"
        p.write_bytes(b"\x00")
        return p


class _FlagFirstScorer:
    """Flags the very first attempt, clears every later attempt (so the first drill's retry
    improves) — and records that it was called more than once."""

    def __init__(self):
        self.calls = 0

    def score(self, wav_path, *, canonical, targets, tip, competitors, drill_id, text, contrast_id):
        self.calls += 1
        if self.calls == 1:
            flag = PhoneFlag(expected="w", word=text, gop=-3.0, competitor=(competitors[0] if competitors else "ɹ"),
                             competitor_margin=1.5, confident_diagnosis=True, tip=tip)
            return DrillResult(drill_id, text, contrast_id, "scored", flags=[flag])
        return DrillResult(drill_id, text, contrast_id, "scored", flags=[])


def test_interview_block_speaks_before_recording_and_retries(tmp_path):
    abort.reset()
    events: list = []

    def _record(out_path, time_budget_seconds, early_exit_event=None):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00")
        events.append(("record", str(out_path)))
        return 0.3

    def _play(wav_path):
        events.append(("play", str(wav_path)))

    bundle = coordinator.PronunciationDrills(
        scorer=_FlagFirstScorer(),
        bank=load_drill_bank(),
        engine_note="note",
        tts_playback=True,
        retries=1,
    )
    # Interactive reader: plenty of "space" so every hear-first proceeds (the record poller may
    # consume a few during recording; extras are harmless).
    reader = FakeKeyReader(["space"] * 200)

    result = coordinator._run_pronunciation_drills(
        drills=bundle,
        record_fn=_record,
        scratch_dir=tmp_path / "scratch",
        early_exit_event=threading.Event(),
        console=coordinator.Console(),
        key_reader=reader,
        ui_sleep=lambda *_: None,
        tts_engine=_FakeTTS(events, tmp_path),
        play_fn=_play,
        weak_contrasts=[],
    )

    # (hear-first) the target was played before the first recording.
    kinds = [e[0] for e in events]
    assert "play" in kinds and "record" in kinds
    assert kinds.index("play") < kinds.index("record"), "the target must be heard before recording"

    # (retry) a flagged item retried and improved.
    assert result is not None
    assert result["summary"]["retried"] >= 1
    assert result["summary"]["improved_on_retry"] >= 1
    first = result["items"][0]
    assert first["flags"], "the first attempt's flags are preserved"
    assert first["retry"]["attempts"] == 2 and first["retry"]["outcome"] == "improved"


def test_retries_zero_means_one_shot(tmp_path):
    abort.reset()

    def _record(out_path, time_budget_seconds, early_exit_event=None):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00")
        return 0.3

    bundle = coordinator.PronunciationDrills(
        scorer=_FlagFirstScorer(), bank=load_drill_bank(), engine_note="n",
        tts_playback=False, retries=0,
    )
    result = coordinator._run_pronunciation_drills(
        drills=bundle,
        record_fn=_record,
        scratch_dir=tmp_path / "scratch",
        early_exit_event=threading.Event(),
        console=coordinator.Console(),
        key_reader=FakeKeyReader(["space"] * 50),
        ui_sleep=lambda *_: None,
        weak_contrasts=[],
    )
    assert result["summary"]["retried"] == 0  # retries=0 → 016 one-shot, never a retry
    assert all("retry" not in it for it in result["items"])
