"""LLM-driven grammar-pattern detector (FR-013).

Per `doc/research_methodology.md`, the seed-5 patterns (FR-013a) are the
documented Persian-L1 / proceduralization fossils that the analyzer ALWAYS
looks for, plus any additional pattern surfaced by the LLM with
`occurrence_count >= 2` (FR-013b). Never asks for or stores an L1
declaration (FR-013c). Every finding includes ≥ 1 verbatim evidence quote
(FR-013).
"""

from __future__ import annotations

import json
import re

from speakloop.asr import Transcript
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.llm import LLMEngine, LLMEngineError

# Seed-5 catalog per research_methodology.md §1.1 + Patterns 1–5/7/8.
SEED_PATTERNS: tuple[str, ...] = (
    "3rd-person singular -s drop (e.g., 'he go', 'the system handle')",
    "auxiliary be/do drop (e.g., 'I studying', 'where you go')",
    "definite-article omission before singular count nouns (e.g., 'on dispatcher', 'use library')",
    "preposition substitution / non-standard prepositions (e.g., 'depend on this' vs 'depend upon')",
    "possessor-order transfer from Persian ezafe (e.g., 'my friend brother' → 'my friend's brother')",
)

SYSTEM_PROMPT = (
    "You are a precise English grammar analyst. You are given three transcripts of "
    "spoken practice attempts by a senior software engineer whose first language is "
    "Persian. Your task is to identify recurring grammar patterns ONLY. "
    "Do NOT comment on pronunciation, vocabulary choice, or content. "
    "Do NOT ask the user for any personal information. "
    "For each pattern: provide a short label, the occurrence_count across the three "
    "transcripts, and a list of evidence objects — each evidence object has the "
    "attempt_ordinal (1, 2, or 3) and a verbatim quote substring from that transcript. "
    "Return ONLY a JSON object of the form: "
    '{"patterns": [{"label": "...", "occurrence_count": N, "evidence": [{"attempt_ordinal": 1, "quote": "..."}], "suggested_fix": "..."}]}. '
    "Patterns to look for in priority order: " + " | ".join(SEED_PATTERNS) + ". "
    "Also surface any other recurring pattern with occurrence_count >= 2. "
    "Omit any seed pattern that does not appear. "
    "Do NOT include <think> blocks."
)


def _user_prompt(transcripts: list[Transcript]) -> str:
    parts = ["Three attempt transcripts follow.\n"]
    for i, t in enumerate(transcripts, start=1):
        parts.append(f"--- Attempt {i} ---\n{t.text.strip()}\n")
    parts.append("\nReturn JSON only.")
    return "\n".join(parts)


def _extract_json(raw: str) -> dict:
    """Pull the first JSON object out of the LLM response."""
    raw = raw.strip()
    if raw.startswith("```"):
        # strip ```json fences
        raw = re.sub(r"^```(?:json)?", "", raw).rstrip("`").strip()
    # If the model emits prose before/after the object, grab the outermost {...}.
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract JSON from LLM response: {raw[:200]}")
    return json.loads(match.group(0))


def _verify_evidence(patterns: list[dict], transcripts: list[Transcript]) -> list[GrammarPattern]:
    """Filter patterns to only those whose evidence quote is a verbatim substring."""
    out: list[GrammarPattern] = []
    for p in patterns:
        label = (p.get("label") or "").strip()
        if not label:
            continue
        evidence_in = p.get("evidence") or []
        verified: list[dict] = []
        for ev in evidence_in:
            try:
                ord_ = int(ev.get("attempt_ordinal"))
                quote = str(ev.get("quote") or "").strip()
            except (TypeError, ValueError):
                continue
            if ord_ < 1 or ord_ > len(transcripts):
                continue
            if not quote:
                continue
            if quote in transcripts[ord_ - 1].text:
                verified.append({"attempt_ordinal": ord_, "quote": quote})
        if not verified:
            continue
        count = int(p.get("occurrence_count") or len(verified))
        if count < 2 and not any(
            seed in label
            for seed in ("3rd-person", "auxiliary", "article", "preposition", "possessor")
        ):
            # FR-013b: open-bucket patterns require occurrence_count >= 2.
            continue
        out.append(
            GrammarPattern(
                label=label,
                occurrence_count=count,
                evidence=verified,
                suggested_fix=(p.get("suggested_fix") or None),
            )
        )
    return out


def analyze(
    transcripts: list[Transcript],
    llm: LLMEngine,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> list[GrammarPattern]:
    """Run the LLM grammar analyzer; return verified GrammarPattern findings."""
    if not transcripts:
        return []
    raw = llm.generate(
        SYSTEM_PROMPT,
        _user_prompt(transcripts),
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if "<think>" in raw:
        # Defensive: per Qwen3-8B leak guard.
        raise LLMEngineError("LLM response contains <think> leakage; engine misconfigured.")

    try:
        payload = _extract_json(raw)
    except (ValueError, json.JSONDecodeError) as e:
        raise LLMEngineError(f"Could not parse LLM grammar response: {e}") from e

    patterns_raw = payload.get("patterns") or []
    if not isinstance(patterns_raw, list):
        raise LLMEngineError("LLM response 'patterns' must be a list.")

    return _verify_evidence(patterns_raw, transcripts)
