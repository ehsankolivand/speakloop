"""T006 (017) — the pure hear → say → see → retry loop (`pronunciation.drill_runner`).

No real model / mic / tty / network: the scorer, `speak`, and `record` are fakes and the
key reader is a `FakeKeyReader`/`NullKeyReader`. Asserts hear-first ordering, the bounded retry,
improvement detection, graceful degradation, and the `DrillQuit` quit signal.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop.pronunciation import build_block_result, run_drill_item, select_drills
from speakloop.pronunciation.drill_bank import Contrast, Drill
from speakloop.pronunciation.drill_runner import DrillQuit
from speakloop.pronunciation.interface import DrillResult, PhoneFlag
from speakloop.sessions.keyboard import FakeKeyReader, NullKeyReader

pytestmark = pytest.mark.unit


def _console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False, width=120)


def _drill(did="vest", cid="v_w", prompt="vest"):
    return Drill(id=did, contrast_id=cid, prompt=prompt, canonical=["v", "ɛ", "s", "t"],
                 targets=[{"index": 0, "word": "vest"}], is_base=True)


_CONTRAST = Contrast(id="v_w", expected="v", competitors=["w"], tip="press teeth to lip")


class _FakeScorer:
    """Flags on the attempts whose 1-based index is in ``flag_on``; clean otherwise."""

    def __init__(self, *, flag_on):
        self.calls = 0
        self._flag_on = set(flag_on)

    def score(self, wav_path, *, canonical, targets, tip, competitors, drill_id, text, contrast_id):
        self.calls += 1
        if self.calls in self._flag_on:
            flag = PhoneFlag(expected="v", word=text, gop=-3.0, competitor="w",
                             competitor_margin=1.5, confident_diagnosis=True, tip=tip)
            return DrillResult(drill_id, text, contrast_id, "scored", flags=[flag])
        return DrillResult(drill_id, text, contrast_id, "scored", flags=[])


def _run(scorer, reader, *, tts_on=True, retries=1, scratch, events=None):
    events = events if events is not None else []
    return run_drill_item(
        _drill(), contrast=_CONTRAST, scorer=scorer,
        speak=lambda t: events.append(("speak", t)),
        record=lambda w, l: events.append(("record", l)),
        key_reader=reader, console=_console(), scratch_dir=scratch,
        retries=retries, tts_on=tts_on, ui_sleep=lambda *_: None,
    ), events


def test_hears_target_before_recording(tmp_path):
    scorer = _FakeScorer(flag_on=set())  # clean → no retry
    item, events = _run(scorer, FakeKeyReader(["space"] * 4), scratch=tmp_path)
    assert events[0] == ("speak", "vest"), "the target must be spoken before anything else"
    assert ("record", "drill: vest") in events
    assert events.index(("speak", "vest")) < events.index(("record", "drill: vest"))
    assert item["status"] == "scored" and not item["flags"]
    assert "retry" not in item  # a clean first attempt never retries


def test_replay_on_demand_then_record(tmp_path):
    scorer = _FakeScorer(flag_on=set())
    # `r` replays the target, then `space` proceeds to record.
    item, events = _run(scorer, FakeKeyReader(["r", "space"]), scratch=tmp_path)
    speaks = [e for e in events if e[0] == "speak"]
    assert len(speaks) == 2, "pressing r must replay the target before recording"
    assert events[-1][0] == "record"


def test_bounded_retry_is_capped(tmp_path):
    scorer = _FakeScorer(flag_on={1, 2, 3, 4})  # always flags
    item, _ = _run(scorer, FakeKeyReader(["space"] * 8), retries=2, scratch=tmp_path)
    assert scorer.calls == 3, "1 first attempt + at most `retries` (2) — never unbounded"
    assert item["flags"], "the first attempt's flags are preserved (016 with_flags semantics)"
    assert item["retry"]["attempts"] == 3
    assert item["retry"]["outcome"] == "still_off"


def test_retry_reports_improvement_and_stops_early(tmp_path):
    scorer = _FakeScorer(flag_on={1})  # flags first, clears on the retry
    item, _ = _run(scorer, FakeKeyReader(["space"] * 8), retries=2, scratch=tmp_path)
    assert scorer.calls == 2, "stops as soon as the target clears"
    assert item["retry"]["attempts"] == 2
    assert item["retry"]["outcome"] == "improved"


def test_noninteractive_degrades_to_016(tmp_path):
    # NullKeyReader (raw_capable False): no replay wait, no retry even when flagged.
    scorer = _FakeScorer(flag_on={1, 2})
    item, events = _run(scorer, NullKeyReader(), retries=2, scratch=tmp_path)
    assert scorer.calls == 1, "non-interactive never retries (the 016 path)"
    assert "retry" not in item
    assert events[0] == ("speak", "vest"), "TTS still plays once even non-interactively"


def test_tts_off_skips_hear_first(tmp_path):
    scorer = _FakeScorer(flag_on=set())
    item, events = _run(scorer, NullKeyReader(), tts_on=False, scratch=tmp_path)
    assert all(e[0] != "speak" for e in events), "tts_on=False must skip playback entirely"
    assert ("record", "drill: vest") in events


def test_q_during_hear_first_raises_drill_quit(tmp_path):
    scorer = _FakeScorer(flag_on=set())
    with pytest.raises(DrillQuit):
        _run(scorer, FakeKeyReader(["q"]), scratch=tmp_path)


def test_build_block_result_summary(tmp_path):
    # Two items: one flagged+improved, one clean → summary aggregates additively.
    items = [
        {"drill_id": "a", "contrast_id": "v_w", "flags": [{"expected": "v"}],
         "retry": {"attempts": 2, "outcome": "improved", "final_flags": []}},
        {"drill_id": "b", "contrast_id": "w_r", "flags": []},
    ]

    class _Bank:
        def contrast(self, cid):
            return _CONTRAST if cid == "v_w" else Contrast(id="w_r", expected="w", competitors=["ɹ"], tip="")

    res = build_block_result(items, bank=_Bank(), engine_note="note")
    s = res["summary"]
    assert s["drills"] == 2 and s["with_flags"] == 1
    assert s["retried"] == 1 and s["improved_on_retry"] == 1
    assert s["tricky_sounds"] == ["v vs w"]
    assert build_block_result([], bank=_Bank()) is None  # no items → no section


def test_select_drills_orders_weak_first_else_curated():
    class _Bank:
        def __init__(self, drills):
            self._d = drills

        def base_drills(self):
            return self._d

    a = _drill("a", "v_w")
    b = _drill("b", "w_r")
    c = _drill("c", "th_s")
    bank = _Bank([a, b, c])
    # No history → curated order unchanged.
    assert [d.id for d in select_drills(bank, weak_contrasts=[], max_base=3)] == ["a", "b", "c"]
    # Weak contrast th_s first, rest keep curated order.
    assert [d.id for d in select_drills(bank, weak_contrasts=["th_s"], max_base=3)] == ["c", "a", "b"]
    # Cap honoured.
    assert [d.id for d in select_drills(bank, weak_contrasts=["w_r"], max_base=2)] == ["b", "a"]
