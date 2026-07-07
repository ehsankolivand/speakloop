"""Unscripted follow-up generation (010-interview-loop, P1).

After the final timed attempt, generate 1–2 follow-up questions derived SOLELY
from the learner's own attempt transcripts (a gap, an edge case, or a "why") —
never from the question bank (FR-001). Each generated follow-up is checked to be
grounded in the learner's own words (a shared content word, or a stated probe
reference) so it satisfies SC-010, and the set is gated by a probe-worthiness
threshold (FR-006).

Reuses the injected ``LLMEngine`` (no engine import — Principle V) and the shared
JSON recovery ladder (``grammar_analyzer._extract_json``). Raises
``LLMEngineError`` on a transient failure / empty response — the coordinator
catches it and simply asks no follow-ups.
"""

from __future__ import annotations

import re

from speakloop.asr import Transcript
from speakloop.feedback.grammar_analyzer import generate_json
from speakloop.llm import LLMEngine

_FOLLOWUPS_MAX_TOKENS = 256
_FOLLOWUPS_TEMPERATURE = 0.4

# Probe-worthiness gate (Key Definitions): need enough real speech to probe.
MIN_PROBE_WORDS = 30
MAX_FOLLOWUPS = 2

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_CONTENT_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']{3,}")  # >= 4 letters


def _content_words(text: str) -> set[str]:
    return {w.lower() for w in _CONTENT_WORD_RE.findall(text or "")}


def _is_grounded(question: str, probe_ref: str, transcript_words: set[str]) -> bool:
    """A follow-up is grounded if it reuses a transcript content word, or names a
    probe reference (the omission/edge-case it targets) — SC-010."""
    if _content_words(question) & transcript_words:
        return True
    return bool(probe_ref.strip())


def generate_followups(
    question_text: str,
    transcripts: list[Transcript],
    llm: LLMEngine,
    *,
    system_prompt: str,
    max_count: int = MAX_FOLLOWUPS,
) -> list[dict]:
    """Return up to ``max_count`` grounded follow-up specs, or [] if not probe-worthy.

    Each spec is ``{"question": str, "probe_ref": str, "probe_type": str}``.
    """
    combined = " ".join(t.text.strip() for t in transcripts).strip()
    if len(_WORD_RE.findall(combined)) < MIN_PROBE_WORDS:
        return []  # FR-006: not enough material to probe — ask zero follow-ups

    transcript_words = _content_words(combined)
    user_prompt = (
        f"Interview question:\n{question_text.strip()}\n\n"
        "The candidate's spoken attempts:\n"
        + "\n".join(f"Attempt {i}: {t.text.strip()}" for i, t in enumerate(transcripts, start=1))
    )
    data = generate_json(
        llm,
        system_prompt,
        user_prompt,
        max_tokens=_FOLLOWUPS_MAX_TOKENS,
        temperature=_FOLLOWUPS_TEMPERATURE,
        empty_message="Follow-up generator returned an empty response.",
    )

    out: list[dict] = []
    for item in data.get("followups") or []:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question", "")).strip()
        probe_ref = str(item.get("probe_ref", "")).strip()
        probe_type = str(item.get("probe_type", "")).strip() or "gap"
        if not q or not _is_grounded(q, probe_ref, transcript_words):
            continue
        out.append({"question": q, "probe_ref": probe_ref, "probe_type": probe_type})
        if len(out) >= max_count:
            break
    return out
