"""LLM-assisted pronunciation-mishearing classification (010-interview-loop, P4).

Runs AFTER the deterministic hallucination filter (``triage/hallucination.py``),
on real-speech text only. Flags likely pronunciation-driven mishearings (e.g.
"must" → "mouse") so they are reported as PRONUNCIATION FLAGS, never as grammar
errors (FR-026). This is pure ENRICHMENT: if no language model is available or the
call fails, mishearing detection is silently skipped — it never raises into the
session loop and the hallucination guarantee (which is heuristic, already applied)
is unaffected.

Reuses the injected ``LLMEngine`` (no engine import — Principle V) and the existing
JSON recovery ladder (``grammar_analyzer._extract_json``).
"""

from __future__ import annotations

from speakloop.feedback.grammar_analyzer import _extract_json
from speakloop.llm import LLMEngine, LLMEngineError
from speakloop.triage.hallucination import TriagedSpan

_MISHEARING_MAX_TOKENS = 256
_MISHEARING_TEMPERATURE = 0.2


def detect_mishearings(
    real_text: str,
    llm: LLMEngine,
    *,
    system_prompt: str,
) -> list[TriagedSpan]:
    """Return pronunciation-flag spans for ``real_text``; [] on any failure.

    Enrichment only — catches ``LLMEngineError`` and parse failures and returns []
    so a degraded model never blocks the session (FR-035 / contract C4)."""
    text = (real_text or "").strip()
    if not text:
        return []
    try:
        raw = llm.generate(
            system_prompt,
            f"Transcript spans to check:\n{text}",
            max_tokens=_MISHEARING_MAX_TOKENS,
            temperature=_MISHEARING_TEMPERATURE,
        )
        data = _extract_json(raw)
    except (LLMEngineError, ValueError):
        return []  # no model / transient failure / unparseable → skip enrichment

    flags: list[TriagedSpan] = []
    for item in data.get("mishearings") or []:
        if not isinstance(item, dict):
            continue
        heard = str(item.get("heard", "")).strip()
        intended = str(item.get("likely_intended", "")).strip()
        span_text = str(item.get("span_text", "")).strip()
        if not heard or not intended or heard.lower() == intended.lower():
            continue
        flags.append(
            TriagedSpan(
                text=span_text or heard,
                start_seconds=0.0,
                end_seconds=0.0,
                span_class="mishearing",
                signal="llm_mishearing",
                heard=heard,
                likely_intended=intended,
            )
        )
    return flags
