"""T009 — domain-context mining + initial_prompt build + sha256 (FR-003).

The domain context is built from the question prompt + ideal answer + tags +
the static seed lexicon + the Persian-accent declaration (research §a). Pure,
deterministic, offline — no model load.
"""

from __future__ import annotations

import hashlib

import pytest

from speakloop.asr import TranscriptionContext
from speakloop.asr.domain_context import ACCENT_DECLARATION, build_context
from speakloop.asr.seed_lexicon import SEED_TERMS
from speakloop.content import Question

pytestmark = pytest.mark.unit

_KOTLIN_Q = Question(
    id="kotlin-coroutines-basics",
    question=(
        "Explain how Kotlin coroutines differ from threads, and when you would "
        "choose one over the other in a high-load Android service."
    ),
    ideal_answer=(
        "Coroutines are a structured-concurrency primitive that runs on a shared "
        "pool of threads. Unlike OS threads, they are cheap to create and suspend "
        "cooperatively rather than blocking. You pick a coroutine for I/O-bound or "
        "cooperative work, and a thread when you have CPU-bound work that genuinely "
        "needs parallel execution."
    ),
    tags=["behavioral", "kotlin", "concurrency"],
)


def test_build_context_returns_transcription_context():
    ctx = build_context(_KOTLIN_Q)
    assert isinstance(ctx, TranscriptionContext)
    assert ctx.use_vad is True
    assert ctx.initial_prompt


def test_prompt_contains_accent_declaration():
    ctx = build_context(_KOTLIN_Q)
    assert ACCENT_DECLARATION in ctx.initial_prompt


@pytest.mark.parametrize(
    "term",
    ["kotlin", "coroutine", "threads", "mutex", "dispatcher", "cpu-bound", "io-bound", "android"],
)
def test_prompt_contains_expected_technical_terms(term):
    # Mined (Kotlin/Android, CPU-bound, I/O-bound→io-bound) + seed (mutex,
    # dispatcher, coroutines, threads). Case-insensitive presence is enough —
    # the initial_prompt is a bias hint, not an exact set.
    prompt = build_context(_KOTLIN_Q).initial_prompt.lower()
    assert term in prompt


def test_sha256_matches_prompt_bytes():
    ctx = build_context(_KOTLIN_Q)
    expected = hashlib.sha256(ctx.initial_prompt.encode("utf-8")).hexdigest()
    assert ctx.initial_prompt_sha256 == expected


def test_seed_lexicon_always_present_even_with_termless_question():
    bare = Question(id="x", question="Tell me about a time.", ideal_answer="I did things.", tags=[])
    ctx = build_context(bare)
    assert ACCENT_DECLARATION in ctx.initial_prompt
    # Every seed term still seeds the bias even when the prompt mentions none.
    low = ctx.initial_prompt.lower()
    for term in SEED_TERMS:
        assert term.lower() in low
