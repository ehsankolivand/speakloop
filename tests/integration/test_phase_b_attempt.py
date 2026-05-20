"""T061 — full Phase B coordinator run with stubs produces one Markdown report."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from speakloop.asr import Transcript, WordTiming
from speakloop.content import Question
from speakloop.sessions import coordinator

pytestmark = pytest.mark.integration


class StubTTS:
    def synthesize(self, text, voice=None):
        return Path("/dev/null")

    def available_voices(self):
        return []


class StubASR:
    def __init__(self, transcripts):
        self._iter = iter(transcripts)

    def transcribe(self, wav_path):
        return next(self._iter)


def _stub_record_factory():
    def record(out_path, time_budget_seconds, early_exit_event):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        # write a 1-byte placeholder so the file exists (ASR is stubbed)
        Path(out_path).write_bytes(b"\x00")
        # short fake duration
        return min(time_budget_seconds, 5.0)

    return record


def test_full_phase_b_session(tmp_sessions_dir, tmp_path):
    q = Question(
        id="kotlin-coroutines-basics",
        question="Explain coroutines",
        ideal_answer="They are lightweight.",
    )
    transcripts = [
        Transcript(
            text="um so a coroutine is a lightweight thread",
            words=[
                WordTiming("um", 0.0, 0.3),
                WordTiming("so", 0.4, 0.6),
                WordTiming("a", 0.7, 0.8),
                WordTiming("coroutine", 0.9, 1.5),
                WordTiming("is", 1.6, 1.8),
                WordTiming("a", 1.9, 2.0),
                WordTiming("lightweight", 2.1, 2.6),
                WordTiming("thread", 2.7, 3.0),
            ],
            audio_duration_seconds=3.0,
        )
        for _ in range(3)
    ]

    path = coordinator.run_session(
        q,
        tts_engine=None,
        play_fn=None,
        asr_engine=StubASR(transcripts),
        record_fn=_stub_record_factory(),
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch",
    ).report_path
    assert path.exists()
    # Exactly one .md
    md_files = list(tmp_sessions_dir.glob("*.md"))
    assert len(md_files) == 1
    # Validate frontmatter
    text = path.read_text()
    assert text.startswith("---\n")
    body_after_fm = text.split("---\n", 2)[1]
    fm = yaml.safe_load(body_after_fm)
    assert fm["generated_by_phase"] == "B"
    assert fm["grammar_patterns"] == []
    assert len(fm["attempts"]) == 3
    expected_metric_keys = {
        "words_total",
        "speech_rate_wpm",
        "filler_words_count",
        "filler_density_per_100_words",
        "pauses_count",
        "mean_pause_ms",
        "self_corrections_count",
    }
    for a in fm["attempts"]:
        assert set(a["metrics"].keys()) == expected_metric_keys


def test_filename_disambiguation_on_repeat(tmp_sessions_dir, tmp_path):
    q = Question(id="kotlin-coroutines-basics", question="Q", ideal_answer="A")
    transcripts = [Transcript(text="x", audio_duration_seconds=1.0) for _ in range(3)]

    p1 = coordinator.run_session(
        q,
        asr_engine=StubASR(list(transcripts)),
        record_fn=_stub_record_factory(),
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch1",
    ).report_path
    p2 = coordinator.run_session(
        q,
        asr_engine=StubASR(list(transcripts)),
        record_fn=_stub_record_factory(),
        sessions_dir=tmp_sessions_dir,
        scratch_dir=tmp_path / "scratch2",
    ).report_path
    assert p1.exists() and p2.exists()
    assert p1 != p2
    assert p2.name.endswith("-2.md")
