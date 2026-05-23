"""V-R4 — no network during a full grammar analysis + report build (SC-006, FR-016).

The 006 feedback path (json-repair recovery, dedupe, deterministic narrative/top-priority,
report assembly) must make ZERO network connections. Mirrors the socket-blocking guard from
test_offline_after_install.py. Uses a stub LLM (no live model), so this is CI-safe and proves
the *feedback* code itself never reaches the network — Principle II.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime

import pytest

from speakloop.asr import Transcript
from speakloop.feedback import grammar_analyzer, narrative, report_builder
from speakloop.feedback.frontmatter import Attempt, AttemptMetrics, Session

pytestmark = pytest.mark.integration


class NetworkAccessError(AssertionError):
    pass


@pytest.fixture
def block_network(monkeypatch):
    opened: list[tuple] = []
    real_socket = socket.socket

    class _BlockedSocket(real_socket):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            opened.append(("__init__", args, kwargs))
            super().__init__(*args, **kwargs)

        def connect(self, address):
            raise NetworkAccessError(f"network attempted: connect({address!r})")

        def connect_ex(self, address):
            raise NetworkAccessError(f"network attempted: connect_ex({address!r})")

    monkeypatch.setattr(socket, "socket", _BlockedSocket)
    yield opened


class _StubLLM:
    def generate(self, system_prompt, user_prompt, max_tokens=2048, temperature=0.7, retry=False):
        return json.dumps(
            {
                "patterns": [
                    {
                        "label": "gerund/infinitive confusion",
                        "occurrence_count": 1,
                        "evidence": [
                            {"attempt_ordinal": 1, "quote": "like to programming", "corrected": "like programming"}
                        ],
                    }
                ]
            }
        )


def _attempt(ordinal, wpm, fill, text):
    return Attempt(
        ordinal=ordinal,
        time_budget_seconds={1: 240, 2: 180, 3: 120}[ordinal],
        actual_duration_seconds=100.0,
        transcript=text,
        metrics=AttemptMetrics(
            words_total=120, speech_rate_wpm=wpm, filler_words_count=int(fill),
            filler_density_per_100_words=fill, pauses_count=3, mean_pause_ms=500.0,
            self_corrections_count=0,
        ),
    )


def test_full_analysis_and_report_make_no_network_connection(block_network):
    transcripts = [
        Transcript(text="I like to programming every day at work here.", audio_duration_seconds=60.0),
        Transcript(text="I build payment systems for a fintech company.", audio_duration_seconds=45.0),
        Transcript(text="Honestly I enjoy building reliable services.", audio_duration_seconds=30.0),
    ]

    # Phase-C grammar analysis (json-repair recovery + dedupe) — no network.
    patterns = grammar_analyzer.analyze(transcripts, _StubLLM())
    assert patterns and patterns[0].catalog_id == "gerund-infinitive-confusion"

    attempts = [_attempt(1, 116, 2.5, transcripts[0].text),
                _attempt(2, 128, 2.0, transcripts[1].text),
                _attempt(3, 138, 1.5, transcripts[2].text)]

    # Deterministic narrative + top-priority + full report build — no network.
    session = Session(
        session_id="2026-05-22-q01",
        started_at=datetime(2026, 5, 22, 10, 0, 0),
        question_id="q01",
        question_text="Describe a system you built.",
        attempts=attempts,
        grammar_patterns=patterns,
        generated_by_phase="C",
        cross_attempt_narrative=narrative.build_narrative(attempts, patterns),
        top_priority=narrative.select_top_priority(patterns, attempts),
    )
    report = report_builder.build(session)
    assert "## Grammar patterns" in report

    assert block_network == [], f"unexpected socket activity: {block_network}"
