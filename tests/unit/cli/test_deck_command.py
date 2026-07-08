"""T024 (018, US1) — the `speakloop deck` command.

No real model / mic / tty: TTS + playback are fakes, `_is_interactive` is patched, and the
store/reports live under tmp. Asserts the loop hears before it reveals, the self-mark reschedules
and persists across runs, `--export` writes an Anki-cloze file without drilling, a non-interactive
run skips cleanly, and NO session report is ever written.
"""

from __future__ import annotations

import io
from datetime import date

import pytest
from rich.console import Console

from speakloop.cli import deck
from speakloop.linecards.cards import LineCard
from speakloop.store import io as store_io

pytestmark = pytest.mark.unit

TODAY = date(2026, 7, 1)
CARD = LineCard("starter:trade", "the trade-off here", "", "name the tension", "", "starter", cloze="trade-off")


def _console():
    return Console(file=io.StringIO(), force_terminal=False, width=120)


class _FakeTTS:
    def __init__(self, events):
        self.events = events

    def synthesize(self, text, voice=None, speed=None):
        self.events.append(("synth", text))
        return f"wav:{text}"


def _run(monkeypatch, tmp_path, *, input_seq, starter=(CARD,), today=TODAY,
         interactive=True, export_path=None, limit=None, store_path=None):
    monkeypatch.setattr(deck, "_is_interactive", lambda: interactive)
    events: list = []
    seq = list(input_seq)
    console = _console()
    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    store_path = store_path or (tmp_path / "store.json")
    deck.run(
        limit=limit,
        export_path=export_path,
        tts_engine=_FakeTTS(events),
        play_fn=lambda w: events.append(("play", w)),
        reports_dir=reports,
        store_path=store_path,
        starter_cards=list(starter),
        today=today,
        input_fn=lambda *_: (seq.pop(0) if seq else "q"),
        console=console,
    )
    return events, console.file.getvalue(), store_path


def test_loop_hears_before_reveal_marks_and_persists(monkeypatch, tmp_path):
    events, out, store_path = _run(monkeypatch, tmp_path, input_seq=["", "3"])  # Enter to reveal, 3=good
    kinds = [e[0] for e in events]
    assert "play" in kinds, "the card must be spoken (heard) first"
    assert ("synth", "the trade-off here") in events
    assert "Better:" in out and "the trade-off here" in out
    # no interview report anywhere
    assert not list(tmp_path.rglob("*.md"))
    # the self-mark rescheduled + persisted the card
    store = store_io.load(store_path)
    row = store.line_cards["starter:trade"]
    assert row["total_reviews"] == 1
    assert row["last_grade"] == "good"
    assert row["next_due"] == "2026-07-03"  # good on a fresh card → base(1)×2 = 2 days out


def test_progress_persists_across_runs(monkeypatch, tmp_path):
    store_path = tmp_path / "store.json"
    _run(monkeypatch, tmp_path, input_seq=["", "3"], today=TODAY, store_path=store_path)
    # next day: the good-marked card (due 07-03) is not yet due → caught up, nothing drilled
    events, out, _ = _run(
        monkeypatch, tmp_path, input_seq=["n"], today=date(2026, 7, 2), store_path=store_path
    )
    assert "caught up" in out.lower()
    assert "play" not in [e[0] for e in events]


def test_quit_stops_cleanly_and_saves(monkeypatch, tmp_path):
    events, out, store_path = _run(monkeypatch, tmp_path, input_seq=["q"])  # quit at the first reveal prompt
    assert "Deck complete" in out
    store = store_io.load(store_path)
    # quitting before marking leaves the card unreviewed
    assert store.line_cards["starter:trade"]["total_reviews"] == 0


def test_export_writes_anki_cloze_without_drilling(monkeypatch, tmp_path):
    out_file = tmp_path / "cards.txt"
    events, out, _ = _run(monkeypatch, tmp_path, input_seq=[], export_path=out_file)
    assert out_file.exists()
    text = out_file.read_text(encoding="utf-8")
    assert "{{c1::trade-off}}" in text
    assert "play" not in [e[0] for e in events], "export must not drill"
    assert not list(tmp_path.rglob("*.md"))


def test_non_interactive_skips_drilling_with_notice(monkeypatch, tmp_path):
    events, out, _ = _run(monkeypatch, tmp_path, input_seq=[], interactive=False)
    assert "skipping" in out.lower()
    assert "play" not in [e[0] for e in events]
    assert not list(tmp_path.rglob("*.md"))
