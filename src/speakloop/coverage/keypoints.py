"""Key-point derivation + ideal-answer content versioning (010, P3).

Derive 5–7 key points from a question's ideal answer once and key them to a
content hash of that answer (research R3), so an edit to the ideal answer triggers
re-derivation. Behavioral questions use the 4 STAR components instead (P5 — see
``star_key_points``); for now the default path derives 5–7.

Reuses the injected ``LLMEngine`` + shared JSON recovery ladder; no engine import.
"""

from __future__ import annotations

import hashlib
import re

from speakloop.feedback.grammar_analyzer import generate_json
from speakloop.llm import LLMEngine

_KEYPOINTS_MAX_TOKENS = 512
_KEYPOINTS_TEMPERATURE = 0.2
MIN_POINTS = 5
MAX_POINTS = 7

_WS_RE = re.compile(r"\s+")

# STAR components for behavioral questions (P5; used by type-aware derivation).
STAR_COMPONENTS = ("Situation", "Task", "Action", "Result")


def ideal_answer_hash(ideal_answer: str) -> str:
    """sha256 (truncated) of the NORMALISED ideal answer (trim + collapse ws + NFC)."""
    import unicodedata

    normalized = _WS_RE.sub(" ", unicodedata.normalize("NFC", (ideal_answer or "")).strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def star_key_points() -> list[dict]:
    """The 4 STAR components as key points (behavioral questions, P5/FR-033)."""
    return [{"id": i, "text": name} for i, name in enumerate(STAR_COMPONENTS, start=1)]


def derive_key_points(
    question_text: str,
    ideal_answer: str,
    question_type: str,
    llm: LLMEngine,
    *,
    system_prompt: str,
) -> list[dict]:
    """Return the key points as ``[{"id": int, "text": str}, ...]``.

    Behavioral → the 4 STAR components (no LLM call). Otherwise derive 5–7 via the
    LLM. Raises ``LLMEngineError`` on empty/failed response (coordinator degrades)."""
    if question_type == "behavioral":
        return star_key_points()

    data = generate_json(
        llm,
        system_prompt,
        f"Interview question:\n{question_text.strip()}\n\nIdeal answer:\n{ideal_answer.strip()}",
        max_tokens=_KEYPOINTS_MAX_TOKENS,
        temperature=_KEYPOINTS_TEMPERATURE,
        empty_message="Key-point derivation returned an empty response.",
    )
    points: list[dict] = []
    for i, text in enumerate(data.get("key_points") or [], start=1):
        t = str(text).strip()
        if t:
            points.append({"id": i, "text": t})
        if len(points) >= MAX_POINTS:
            break
    return points
