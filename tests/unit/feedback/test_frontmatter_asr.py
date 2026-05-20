"""T010 — additive `asr:` provenance block; schema_version stays 1 (FR-007/FR-008).

The `asr:` top-level key is emitted ONLY when `session.asr` is present, so v1 /
Phase-B reports stay byte-identical and the trends reader keeps working.
"""

from __future__ import annotations

from datetime import datetime

import frontmatter as fm_lib
import pytest
import yaml

from speakloop.feedback import frontmatter

pytestmark = pytest.mark.unit


def _make_session(asr=None):
    return frontmatter.Session(
        session_id="2026-05-20-kotlin",
        started_at=datetime(2026, 5, 20, 10, 0, 0),
        question_id="kotlin-coroutines-basics",
        question_text="Explain how Kotlin coroutines differ from threads.",
        attempts=[
            frontmatter.Attempt(
                ordinal=1,
                time_budget_seconds=240,
                actual_duration_seconds=200.0,
                metrics=frontmatter.AttemptMetrics(words_total=100, speech_rate_wpm=110.0),
            )
        ],
        grammar_patterns=[],
        generated_by_phase="C",
        asr=asr,
    )


def _whisper_provenance():
    return frontmatter.AsrProvenance(
        engine="whisper",
        model="mlx-community/whisper-large-v3-turbo",
        initial_prompt="The following is technical English spoken with a Persian accent. coroutines",
        initial_prompt_sha256="a1b2c3",
        vad={
            "engine": "silero",
            "speech_threshold": 0.5,
            "min_speech_ms": 250,
            "min_silence_ms": 100,
            "merge_gap_ms": 300,
            "speech_pad_ms": 30,
        },
        fell_back=False,
    )


def test_asr_block_emitted_and_schema_stays_1():
    text = frontmatter.dump(_make_session(asr=_whisper_provenance()))
    assert "asr:" in text
    body = yaml.safe_load(text.replace("---\n", "", 1).rstrip("-\n"))
    assert body["schema_version"] == 1
    assert body["asr"]["engine"] == "whisper"
    assert body["asr"]["model"] == "mlx-community/whisper-large-v3-turbo"
    assert body["asr"]["initial_prompt_sha256"] == "a1b2c3"
    assert body["asr"]["vad"]["merge_gap_ms"] == 300
    assert body["asr"]["fell_back"] is False


def test_asr_block_round_trips_through_parse():
    text = frontmatter.dump(_make_session(asr=_whisper_provenance()))
    parsed = frontmatter.parse(text)
    assert parsed.asr is not None
    assert parsed.asr.engine == "whisper"
    assert parsed.asr.initial_prompt_sha256 == "a1b2c3"
    assert parsed.asr.fell_back is False
    assert parsed.asr.vad["merge_gap_ms"] == 300


def test_no_asr_key_when_absent():
    text = frontmatter.dump(_make_session(asr=None))
    assert "asr:" not in text
    assert frontmatter.parse(text).asr is None


def test_fallback_provenance_records_engine_actually_used():
    prov = frontmatter.AsrProvenance(
        engine="parakeet",
        model="mlx-community/parakeet-tdt-0.6b-v3",
        initial_prompt="…",
        initial_prompt_sha256="deadbeef",
        vad=None,
        fell_back=True,
    )
    text = frontmatter.dump(_make_session(asr=prov))
    parsed = frontmatter.parse(text)
    assert parsed.asr.engine == "parakeet"
    assert parsed.asr.fell_back is True
    assert parsed.asr.vad is None


def test_asr_bearing_report_still_parses_as_plain_frontmatter():
    """The trends reader uses python-frontmatter + a fixed key set; an unknown
    `asr:` key must not break it (FR-008)."""
    text = frontmatter.dump(_make_session(asr=_whisper_provenance()))
    report = f"{text}\n# Body\n"
    post = fm_lib.loads(report)
    assert post["schema_version"] == 1
    assert "attempts" in post.metadata
    assert "generated_by_phase" in post.metadata
