"""Catalog-aware LLM grammar-pattern detector (FR-001..FR-009).

The analyzer is anchored to the Persian-L1 error catalog
(``feedback/catalog.py``): the catalog's ``detection_hints`` are injected into
the prompt so labels are accurate, and the learner-facing ``transfer_reason``
(the "Because:" line) and the deterministic ``impact_rank`` come from the catalog
rather than the model. The LLM's job is narrowed to (1) spotting occurrences and
(2) supplying a corrected rewrite (the "Better:" line) per evidence quote, plus a
one-line reason for any open-bucket pattern not in the catalog.

Every finding is then verified deterministically (research.md §b/§e):

* each evidence ``quote`` must be a verbatim substring of its attempt (FR-007),
* then survive the coherence filter (FR-006) — ASR garble is dropped,
* a corrected version that equals the quote is treated as no fix; a pattern
  whose only correction equals the quote is suppressed (FR-009),
* open-bucket (non-catalog) patterns require ``occurrence_count >= 2`` and a
  non-empty explanation (FR-002),
* patterns are returned sorted ascending by
  ``(impact_rank, -occurrence_count, first_attempt_ordinal)`` (FR-005).
"""

from __future__ import annotations

import json
import re

from speakloop.asr import Transcript
from speakloop.feedback import catalog as catalog_mod
from speakloop.feedback import coherence
from speakloop.feedback.catalog import OPEN_BUCKET_IMPACT_RANK
from speakloop.feedback.frontmatter import GrammarPattern
from speakloop.llm import LLMEngine, LLMEngineError


def _catalog_block() -> str:
    """Render the catalog labels + detection hints for the system prompt."""
    lines: list[str] = []
    for entry in catalog_mod.get_catalog().entries:
        hints = "; ".join(entry.detection_hints) if entry.detection_hints else ""
        lines.append(f"- {entry.label}: {hints}" if hints else f"- {entry.label}")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    return (
        "You are a precise English grammar analyst. You are given three transcripts "
        "of spoken practice attempts by a senior software engineer whose first "
        "language is Persian. Identify recurring grammar patterns ONLY. Do NOT "
        "comment on pronunciation, vocabulary choice, or content. Do NOT ask the "
        "user for any personal information.\n\n"
        "For each pattern provide: a short label, the occurrence_count across the "
        "three transcripts, and a list of evidence objects. Each evidence object has "
        "attempt_ordinal (1, 2, or 3), a verbatim quote substring from that "
        "transcript, and a corrected rewrite of that quote.\n\n"
        "Use these EXACT labels when the pattern matches one of them:\n"
        f"{_catalog_block()}\n\n"
        "You MAY also surface any other recurring pattern (occurrence_count >= 2) "
        "with a label of your own; for those, ALSO include a one-line 'explanation' "
        "of why a Persian speaker makes the error. Omit any pattern that does not "
        "appear. Do NOT cite garbled or non-grammatical fragments as evidence.\n\n"
        'Return ONLY a JSON object: {"patterns": [{"label": "...", '
        '"occurrence_count": N, "explanation": "...", "evidence": [{"attempt_ordinal": '
        '1, "quote": "...", "corrected": "..."}]}]}. '
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
        raw = re.sub(r"^```(?:json)?", "", raw).rstrip("`").strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract JSON from LLM response: {raw[:200]}")
    return json.loads(match.group(0))


def _first_attempt_ordinal(pattern: GrammarPattern) -> int:
    return min((ev.get("attempt_ordinal", 99) for ev in pattern.evidence), default=99)


def _verify_and_enrich(
    patterns: list[dict], transcripts: list[Transcript]
) -> list[GrammarPattern]:
    """Verify evidence, attach catalog metadata, suppress no-op fixes, and rank."""
    cat = catalog_mod.get_catalog()
    is_coherent = coherence.make_filter(transcripts)
    out: list[GrammarPattern] = []

    for p in patterns:
        label = (p.get("label") or "").strip()
        if not label:
            continue
        entry = cat.get(label)

        verified: list[dict] = []
        correction_offered = False
        correction_meaningful = False
        for ev in p.get("evidence") or []:
            try:
                ord_ = int(ev.get("attempt_ordinal"))
                quote = str(ev.get("quote") or "").strip()
            except (TypeError, ValueError):
                continue
            if ord_ < 1 or ord_ > len(transcripts) or not quote:
                continue
            if quote not in transcripts[ord_ - 1].text:  # FR-007 verbatim guarantee
                continue
            if not is_coherent(quote):  # FR-006 — runs AFTER the verbatim check
                continue
            item: dict = {"attempt_ordinal": ord_, "quote": quote}
            corrected = str(ev.get("corrected") or "").strip()
            if corrected:
                correction_offered = True
                if corrected != quote:  # FR-009 — a fix equal to the quote is no fix
                    item["corrected"] = corrected
                    correction_meaningful = True
            verified.append(item)

        if not verified:
            continue  # no coherent verbatim evidence → drop the pattern
        if correction_offered and not correction_meaningful:
            continue  # FR-009: the only "fix" equals the quote → suppress

        count = int(p.get("occurrence_count") or len(verified))

        if entry is not None:
            label = entry.label  # normalise to the canonical catalog label
            explanation = entry.transfer_reason
            impact_rank = entry.impact_rank
            catalog_id: str | None = entry.id
        else:
            # Open-bucket: must recur and carry a non-empty reason (FR-002).
            if count < 2:
                continue
            explanation = (p.get("explanation") or "").strip()
            if not explanation:
                continue
            impact_rank = OPEN_BUCKET_IMPACT_RANK
            catalog_id = None

        out.append(
            GrammarPattern(
                label=label,
                occurrence_count=count,
                evidence=verified,
                suggested_fix=(p.get("suggested_fix") or None),
                explanation=explanation,
                impact_rank=impact_rank,
                catalog_id=catalog_id,
            )
        )

    # FR-005: deterministic impact order; ties → more frequent, then earliest.
    out.sort(
        key=lambda p: (
            p.impact_rank if p.impact_rank is not None else OPEN_BUCKET_IMPACT_RANK,
            -p.occurrence_count,
            _first_attempt_ordinal(p),
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
    """Run the catalog-aware grammar analyzer; return verified, ranked findings."""
    if not transcripts:
        return []
    raw = llm.generate(
        _build_system_prompt(),
        _user_prompt(transcripts),
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if "<think>" in raw:
        raise LLMEngineError("LLM response contains <think> leakage; engine misconfigured.")

    try:
        payload = _extract_json(raw)
    except (ValueError, json.JSONDecodeError) as e:
        raise LLMEngineError(f"Could not parse LLM grammar response: {e}") from e

    patterns_raw = payload.get("patterns") or []
    if not isinstance(patterns_raw, list):
        raise LLMEngineError("LLM response 'patterns' must be a list.")

    return _verify_and_enrich(patterns_raw, transcripts)
