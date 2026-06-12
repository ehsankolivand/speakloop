"""017 P0/P2 — failure surfacing + the focused per-sound teaching beat + respellings.

No model / mic / tty / network: the scorer + speak/teach/record are fakes, the key reader is a
``FakeKeyReader``/``NullKeyReader``. Covers:

* P0 — a record exception (mic) and a scorer ``error``/``not_captured`` are surfaced with an
  ACTIONABLE, cause-distinguishing message (never a silent "could not score"), with the raw
  reason shown only under SPEAKLOOP_DEBUG;
* P2 — the curated respelling is shown with the drill, and on a flagged sound the flagged word
  is replayed in ISOLATION via the slower ``teach_speak`` BEFORE the bounded retry.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop.pronunciation.drill_bank import Contrast, Drill
from speakloop.pronunciation.drill_runner import run_drill_item
from speakloop.pronunciation.interface import DrillResult, PhoneFlag
from speakloop.sessions.keyboard import FakeKeyReader, NullKeyReader

pytestmark = pytest.mark.unit


def _console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False, width=200)


def _drill(say_like="WE sounds like 'WEE' — round your lips for /w/."):
    return Drill(
        id="wr-sentence", contrast_id="w_r", prompt="We read the list.",
        canonical=["w", "iː"], targets=[{"index": 0, "word": "we"}], is_base=True,
        say_like=say_like,
    )


_CONTRAST = Contrast(id="w_r", expected="w", competitors=["ɹ"], tip="round your lips")


class _StatusScorer:
    """Returns a fixed status/detail every call (model/scoring outcome)."""

    def __init__(self, status, detail=""):
        self._status, self._detail = status, detail

    def score(self, wav_path, **k):
        return DrillResult("wr-sentence", "We read the list.", "w_r", self._status, detail=self._detail)


def _run(*, scorer, record, reader, console, teach=None, retries=1, drill=None, events=None):
    events = events if events is not None else []
    return run_drill_item(
        drill or _drill(), contrast=_CONTRAST, scorer=scorer,
        speak=lambda t: events.append(("speak", t)),
        record=record, key_reader=reader, console=console, scratch_dir="/tmp",
        retries=retries, tts_on=True, ui_sleep=lambda *_: None,
        teach_speak=teach or (lambda t: events.append(("teach", t))),
    ), events


# --- P0: failure surfacing ---------------------------------------------------------------


def test_record_exception_surfaces_actionable_mic_message():
    def rec(w, l):
        raise RuntimeError("Recording failed: PortAudioError -9986.")

    console = _console()
    item, _ = _run(scorer=_StatusScorer("scored"), record=rec, reader=NullKeyReader(), console=console)
    out = console.file.getvalue()
    assert item["status"] == "error"
    assert "couldn't score that one" in out.lower()
    assert "microphone" in out.lower(), "a mic failure must point at the microphone"


def test_model_error_surfaces_actionable_model_message_and_debug_detail(monkeypatch):
    detail = "could not load pronunciation model: espeak not installed on your system"
    scorer = _StatusScorer("error", detail=detail)

    # default (no debug): actionable model hint + a pointer to --debug, but NOT the raw detail.
    monkeypatch.setenv("SPEAKLOOP_DEBUG", "0")
    console = _console()
    _run(scorer=scorer, record=lambda w, l: None, reader=NullKeyReader(), console=console)
    out = console.file.getvalue()
    assert "scoring model" in out.lower()
    assert "--debug" in out
    assert "espeak" not in out, "raw detail must stay hidden unless debug is on"

    # debug on: the real swallowed reason is shown inline.
    monkeypatch.setenv("SPEAKLOOP_DEBUG", "1")
    console = _console()
    _run(scorer=scorer, record=lambda w, l: None, reader=NullKeyReader(), console=console)
    out = console.file.getvalue()
    assert "espeak not installed" in out, "debug mode must surface the swallowed reason"


def test_not_captured_shows_microphone_hint():
    console = _console()
    item, _ = _run(
        scorer=_StatusScorer("not_captured"), record=lambda w, l: None,
        reader=NullKeyReader(), console=console,
    )
    out = console.file.getvalue()
    assert item["status"] == "not_captured"
    assert "didn't catch any audio" in out.lower()


# --- P2: respelling + teaching beat ------------------------------------------------------


def test_respelling_is_shown_with_the_drill():
    console = _console()
    _run(scorer=_StatusScorer("scored"), record=lambda w, l: None, reader=NullKeyReader(), console=console)
    out = console.file.getvalue()
    assert "Say it like" in out
    assert "WEE" in out, "the curated respelling must be shown with the drill"


class _FlagThenCleanScorer:
    """Flags the target on attempt 1 (word taken from the drill), clears on attempt 2."""

    def __init__(self):
        self.calls = 0

    def score(self, wav_path, *, canonical, targets, tip, competitors, drill_id, text, contrast_id):
        self.calls += 1
        if self.calls == 1:
            t = targets[0]
            flag = PhoneFlag(expected=canonical[t["index"]], word=t["word"], gop=-3.0,
                             competitor="ɹ", competitor_margin=2.0, confident_diagnosis=True, tip=tip)
            return DrillResult(drill_id, text, contrast_id, "scored", flags=[flag])
        return DrillResult(drill_id, text, contrast_id, "scored", flags=[])


def test_teaching_beat_replays_flagged_word_slower_before_the_retry():
    # Interactive + flagged → the teaching beat models JUST the flagged word via teach_speak
    # BEFORE the retry records again. Two hear-first waits (first attempt, retry) → two "space".
    events: list = []
    console = _console()
    item, events = _run(
        scorer=_FlagThenCleanScorer(),
        record=lambda w, l: events.append(("record", l)),
        reader=FakeKeyReader(["space", "space"]), console=console, retries=1, events=events,
    )
    teach_events = [e for e in events if e[0] == "teach"]
    assert teach_events == [("teach", "we")], "the flagged word must be modelled in isolation"
    # ordering: teach happens after the FIRST record and before the retry (second) record.
    teach_i = events.index(("teach", "we"))
    record_is = [i for i, e in enumerate(events) if e[0] == "record"]
    assert len(record_is) == 2
    assert record_is[0] < teach_i < record_is[1]
    # the retry cleared → improvement detected.
    assert item["retry"]["outcome"] == "improved"
    out = console.file.getvalue()
    assert "Let me show you" in out and "Say it like" in out


def test_teaching_beat_falls_back_to_speak_when_no_slower_voice():
    # When no teach_speak is injected, the beat still models the word via the normal speak.
    events: list = []
    console = _console()
    run_drill_item(
        _drill(), contrast=_CONTRAST, scorer=_FlagThenCleanScorer(),
        speak=lambda t: events.append(("speak", t)),
        record=lambda w, l: events.append(("record", l)),
        key_reader=FakeKeyReader(["space", "space"]), console=console, scratch_dir="/tmp",
        retries=1, tts_on=True, ui_sleep=lambda *_: None, teach_speak=None,
    )
    # the word "we" is spoken in isolation during the beat (in addition to the sentence prompt).
    assert ("speak", "we") in events
