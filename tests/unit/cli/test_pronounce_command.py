"""T021 (017) — the standalone `speakloop pronounce` command.

No real model / mic / tty / network: the scorer, bank, TTS, playback, recorder, and key reader
are fakes, and the RAM-only gate is patched. Asserts the loop runs (hear before record), the
RAM-only gate skips without building when unsafe, declining provisioning exits cleanly, no
interview report is written, and the cross-session weak-sound tally is updated.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop import pronunciation
from speakloop.cli import pronounce
from speakloop.pronunciation.gate import SafetyDecision
from speakloop.pronunciation.interface import DrillResult, PhoneFlag
from speakloop.sessions.keyboard import FakeKeyReader, NullKeyReader
from speakloop.store import io as store_io

pytestmark = pytest.mark.unit


def _console():
    return Console(file=io.StringIO(), force_terminal=False, width=120)


def _patch_gate(monkeypatch, *, safe):
    monkeypatch.setattr(
        pronunciation, "assess_standalone_safety",
        lambda **kw: SafetyDecision(safe=safe, reason="r", available_mb=8000, engine="standalone"),
    )


class _FakeTTS:
    def __init__(self, events, tmp):
        self.events, self._tmp = events, tmp

    def synthesize(self, text, voice=None):
        self.events.append(("synth", text))
        p = self._tmp / "tts.wav"
        p.write_bytes(b"\x00")
        return p


class _NeverFlag:
    def __init__(self):
        self.calls = 0

    def score(self, wav_path, **kw):
        self.calls += 1
        return DrillResult(kw["drill_id"], kw["text"], kw["contrast_id"], "scored", flags=[])


class _FlagFirst:
    def __init__(self):
        self.calls = 0

    def score(self, wav_path, **kw):
        self.calls += 1
        if self.calls == 1:
            f = PhoneFlag(expected="v", word=kw["text"], gop=-3.0, competitor="w",
                          competitor_margin=1.5, confident_diagnosis=True, tip=kw["tip"])
            return DrillResult(kw["drill_id"], kw["text"], kw["contrast_id"], "scored", flags=[f])
        return DrillResult(kw["drill_id"], kw["text"], kw["contrast_id"], "scored", flags=[])


def _run(monkeypatch, tmp_path, *, scorer, reader, events, input_seq, interactive=True, limit=2):
    monkeypatch.setattr(pronounce, "_is_interactive", lambda: interactive)
    seq = list(input_seq)
    console = _console()
    store_path = tmp_path / "store.json"

    def _record(out_path, time_budget_seconds, early_exit_event=None):
        events.append(("record", str(out_path)))
        return 0.2

    pronounce.run(
        limit=limit,
        tts_engine=_FakeTTS(events, tmp_path),
        play_fn=lambda w: events.append(("play", str(w))),
        record_fn=_record,
        scorer=scorer,
        bank=pronunciation.load_drill_bank(),
        key_reader=reader,
        store_path=store_path,
        scratch_dir=tmp_path / "scratch",
        input_fn=lambda *_: (seq.pop(0) if seq else "n"),
        console=console,
    )
    return console.file.getvalue(), store_path


def test_loop_runs_hears_before_record_and_writes_no_report(monkeypatch, tmp_path):
    _patch_gate(monkeypatch, safe=True)
    events: list = []
    out, store_path = _run(
        monkeypatch, tmp_path, scorer=_NeverFlag(),
        reader=FakeKeyReader(["space"] * 50), events=events, input_seq=["n"], limit=2,
    )
    kinds = [e[0] for e in events]
    assert "play" in kinds and "record" in kinds
    assert kinds.index("play") < kinds.index("record"), "must hear the target before recording"
    assert "Practice summary" in out
    # No interview report anywhere — only the store file is written.
    assert not list(tmp_path.rglob("*.md")), "standalone must not write a session report"
    assert store_path.exists()


def test_unsafe_noninteractive_skips_without_building(monkeypatch, tmp_path):
    _patch_gate(monkeypatch, safe=False)
    events: list = []
    out, _ = _run(
        monkeypatch, tmp_path, scorer=_NeverFlag(), reader=NullKeyReader(),
        events=events, input_seq=[], interactive=False, limit=2,
    )
    assert "skipped" in out.lower()
    assert events == [], "an unsafe non-interactive run must not record or play anything"


def test_unsafe_override_then_runs(monkeypatch, tmp_path):
    _patch_gate(monkeypatch, safe=False)
    events: list = []
    # interactive: first prompt = freeze-warned override ("yes"), then the round prompt ("n").
    out, _ = _run(
        monkeypatch, tmp_path, scorer=_NeverFlag(), reader=FakeKeyReader(["space"] * 50),
        events=events, input_seq=["yes", "n"], interactive=True, limit=1,
    )
    assert "Override accepted" in out
    assert ("record" in [e[0] for e in events])


def test_retry_updates_weak_sound_tally(monkeypatch, tmp_path):
    _patch_gate(monkeypatch, safe=True)
    events: list = []
    out, store_path = _run(
        monkeypatch, tmp_path, scorer=_FlagFirst(),
        reader=FakeKeyReader(["space"] * 80), events=events, input_seq=["n"], limit=1,
    )
    assert "Practice summary" in out
    store = store_io.load(store_path)
    # the first base drill flagged → its contrast is recorded in the cross-session tally.
    assert store.pronunciation_contrasts, "a flagged contrast must be tallied for future runs"


def test_declining_provisioning_exits_clean(monkeypatch, tmp_path):
    _patch_gate(monkeypatch, safe=True)
    monkeypatch.setattr(pronounce, "_is_interactive", lambda: False)
    import speakloop.installer as installer

    def _decline(*a, **k):
        raise installer.InstallDeclinedError("no")

    monkeypatch.setattr(installer, "ensure_models", _decline)
    console = _console()
    # No scorer/tts/bank injected → need_build True → provisioning runs (and declines).
    pronounce.run(store_path=tmp_path / "s.json", scratch_dir=tmp_path / "sc",
                  input_fn=lambda *_: "n", console=console)
    assert "declined" in console.file.getvalue().lower()
