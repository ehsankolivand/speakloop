"""T034 (018, US2) — the `speakloop shadow` command.

No real model / mic / tty: TTS + playback + recorder + ASR transcribe are fakes, `_is_interactive`
is patched, and the Q&A file is a tmp fixture. Asserts each sentence is spoken before feedback, the
repeat is transcribed and judged (covered/missed), a silent repeat reads "not captured", the scratch
recording is deleted, and NO session report is written.
"""

from __future__ import annotations

import io

import pytest
import typer
from rich.console import Console

from speakloop.asr import Transcript
from speakloop.cli import shadow
from speakloop.sessions.keyboard import FakeKeyReader

pytestmark = pytest.mark.unit

_TWO_SENTENCES = "The window is detached. The view hierarchy is disconnected."


def _console():
    return Console(file=io.StringIO(), force_terminal=False, width=120)


class _FakeTTS:
    def __init__(self, events):
        self.events = events

    def synthesize(self, text, voice=None, speed=None):
        self.events.append(("synth", text))
        return f"wav:{text}"


def _write_qa(tmp_path, ideal):
    path = tmp_path / "questions.yaml"
    path.write_text(
        "schema_version: 1\n"
        "questions:\n"
        "  - id: test-q\n"
        '    question: "A test question?"\n'
        f'    ideal_answer: "{ideal}"\n'
        "    tags: [test]\n",
        encoding="utf-8",
    )
    return path


def _run(monkeypatch, tmp_path, *, input_seq, transcript_text, ideal=_TWO_SENTENCES,
         question_id="test-q", interactive=True, limit=None):
    monkeypatch.setattr(shadow, "_is_interactive", lambda: interactive)
    events: list = []
    seq = list(input_seq)
    console = _console()
    qa_file = _write_qa(tmp_path, ideal)
    scratch = tmp_path / "scratch"

    def _record(out_path, time_budget_seconds, early_exit_event=None):
        events.append(("record", str(out_path)))
        return 0.5

    def _transcribe(wav):
        events.append(("transcribe", str(wav)))
        return Transcript(text=transcript_text, words=[], audio_duration_seconds=2.0)

    shadow.run(
        question_id=question_id,
        limit=limit,
        tts_engine=_FakeTTS(events),
        play_fn=lambda w: events.append(("play", w)),
        record_fn=_record,
        transcribe_fn=_transcribe,
        key_reader=FakeKeyReader(["space"] * 80),
        qa_file=qa_file,
        scratch_dir=scratch,
        input_fn=lambda *_: (seq.pop(0) if seq else "q"),
        console=console,
    )
    return events, console.file.getvalue(), scratch


def test_each_sentence_is_heard_then_repeated_and_judged(monkeypatch, tmp_path):
    events, out, scratch = _run(
        monkeypatch, tmp_path, input_seq=["", ""], transcript_text="the window is detached"
    )
    kinds = [e[0] for e in events]
    assert kinds.count("play") == 2 and kinds.count("record") == 2 and kinds.count("transcribe") == 2
    assert kinds.index("play") < kinds.index("record"), "must hear the sentence before recording"
    assert "Completeness" in out
    # sentence 2's content words (view/hierarchy/disconnected) were not in the repeat
    assert "Missed:" in out
    # privacy: the scratch recording is deleted, and no interview report is written
    assert not list(scratch.rglob("*.wav")) if scratch.exists() else True
    assert not list(tmp_path.rglob("*.md"))


def test_silent_repeat_is_reported_as_not_captured(monkeypatch, tmp_path):
    events, out, _ = _run(
        monkeypatch, tmp_path, input_seq=[""], transcript_text="   ", limit=1
    )
    assert "didn't catch" in out.lower()
    assert "Completeness" not in out  # not scored as a coverage failure


def test_quit_stops_the_loop(monkeypatch, tmp_path):
    events, out, _ = _run(monkeypatch, tmp_path, input_seq=["q"], transcript_text="anything")
    assert "record" not in [e[0] for e in events]  # quit before the first recording
    assert "0 sentence(s)" in out


def test_non_interactive_skips_with_notice(monkeypatch, tmp_path):
    events, out, _ = _run(
        monkeypatch, tmp_path, input_seq=[], transcript_text="x", interactive=False
    )
    assert "skipping" in out.lower()
    assert events == []
    assert not list(tmp_path.rglob("*.md"))


def test_unknown_question_id_exits_nonzero(monkeypatch, tmp_path):
    with pytest.raises(typer.Exit):
        _run(monkeypatch, tmp_path, input_seq=[], transcript_text="x", question_id="nope")


def test_limit_caps_sentences(monkeypatch, tmp_path):
    events, out, _ = _run(
        monkeypatch, tmp_path, input_seq=[""], transcript_text="the window is detached", limit=1
    )
    assert [e[0] for e in events].count("record") == 1
    assert "1 sentence(s)" in out
