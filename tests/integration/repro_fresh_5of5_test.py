"""T012 — fresh 5/5 transcript-trust gate (Clarification Q1, distinct from SC-A).

LOCAL-ONLY. On five clean re-recordings of clearly-pronounced target terms, each
term must transcribe correctly in ALL five attempts (5/5), not just 4/5. This is
the stricter "Transcript trust" gate on fresh, clear audio — separate from the
SC-A 4/5 gate on the original noisy recordings. Skips cleanly without audio.

Layout (off-repo, never committed):
    tests/fixtures/repro_kotlin_coroutines/fresh/
        fresh-1.wav … fresh-5.wav
        fresh_terms.yaml   # {terms: [Kotlin, coroutine, dispatcher, MVI, ...]}

Run with:  uv run pytest -m repro -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.repro

FRESH = Path(__file__).parent.parent / "fixtures" / "repro_kotlin_coroutines" / "fresh"


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


def test_clearly_pronounced_terms_correct_in_all_five_attempts():
    wavs = sorted(FRESH.glob("fresh-*.wav"))
    terms_file = FRESH / "fresh_terms.yaml"
    if len(wavs) < 5 or not terms_file.exists():
        pytest.skip(
            f"Need 5 fresh-*.wav + fresh_terms.yaml in {FRESH} for the 5/5 trust gate "
            "(Clarification Q1). Skipping."
        )

    terms = [t.lower() for t in yaml.safe_load(terms_file.read_text())["terms"]]

    from speakloop.asr.domain_context import build_context
    from speakloop.asr.whisper_mlx_engine import WhisperMLXEngine
    from speakloop.content.schema import Question

    engine = WhisperMLXEngine()
    engine.ensure_loaded()
    ctx = build_context(
        Question(
            id="fresh",
            question="Kotlin coroutines, dispatcher, MVI, Jetpack Compose, mutex, threads.",
            ideal_answer="",
            tags=["kotlin"],
        )
    )
    transcripts = [engine.transcribe(w, context=ctx).text for w in wavs[:5]]

    missing = {}
    for term in terms:
        present = sum(
            1
            for t in transcripts
            if (term in t.lower() if " " in term else term in _tokens(t))
        )
        if present < 5:
            missing[term] = present
    assert not missing, f"Terms not correct in all 5 attempts (term -> count): {missing}"
