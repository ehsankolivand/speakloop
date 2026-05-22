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
import os
import re
from collections import Counter
from datetime import UTC, datetime

import json_repair

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
        '1, "quote": "...", "corrected": "..."}]}]}.\n\n'
        "OUTPUT FORMAT — STRICT JSON, no exceptions:\n"
        '- Use double quotes (") for EVERY key and EVERY string value. Never use '
        "single quotes (').\n"
        "- Do NOT put a trailing comma before a closing } or ].\n"
        "- Do NOT wrap the JSON in markdown code fences (no ``` and no ```json).\n"
        "- Do NOT emit any prose, preamble, or commentary before or after the JSON.\n"
        "- Do NOT include <think> blocks.\n"
        "- Emit the single JSON object and nothing else."
    )


def _user_prompt(transcripts: list[Transcript]) -> str:
    parts = ["Three attempt transcripts follow.\n"]
    for i, t in enumerate(transcripts, start=1):
        parts.append(f"--- Attempt {i} ---\n{t.text.strip()}\n")
    parts.append(
        "\nReturn STRICT JSON only: double quotes on all keys and strings, no "
        "trailing commas, no markdown fences, no extra text."
    )
    return "\n".join(parts)


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", flags=re.DOTALL | re.IGNORECASE)
def _strip_code_fences(raw: str) -> str:
    """Remove a surrounding markdown code fence (```json ... ``` or ``` ... ```)."""
    m = _FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()
    # Fence markers without a clean closing pair: drop stray ``` lines.
    return re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()


def _extract_json(raw: str) -> dict:
    """Recover the grammar payload from the LLM response (recovery ladder —
    contracts/grammar-output-schema.md §C; research Decision 3):

    1. strict ``json.loads`` of the fence-stripped text,
    2. strict parse of the first ``{...}`` region (tolerates surrounding prose),
    3. ``json_repair`` on the full text — recovers single/bare-quoted keys,
       trailing commas, junk-token-before-key, AND truncated/unclosed objects
       (the case the old hand-rolled regex repair could not handle),
    4. ``json_repair`` on just the ``{...}`` region as a last resort.

    Raises ``ValueError`` only when nothing yields a JSON object (then analyze()
    may bounded-regenerate once, else fall back gracefully)."""
    raw = _strip_code_fences(raw.strip())
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    repaired = json_repair.loads(raw)
    if isinstance(repaired, dict) and repaired:
        return repaired
    if match:
        repaired = json_repair.loads(match.group(0))
        if isinstance(repaired, dict) and repaired:
            return repaired

    raise ValueError(f"Could not extract JSON from LLM response: {raw[:200]}")


def _looks_like_repetition_loop(text: str) -> bool:
    """Detect degenerate repetition (the 4-bit loop / truncation signature) so the
    analyzer can trigger ONE bounded regenerate (FR-002). Deliberately conservative
    and JSON-safe — well-formed structured output repeats *keys* with varied values,
    so neither signal below fires on it; a false positive only costs one extra
    (bounded) generation, never a hang."""
    s = (text or "").strip()
    if not s:
        return False
    words = s.split()
    run = max_run = 1  # the same token repeated many times in a row
    for a, b in zip(words, words[1:]):
        run = run + 1 if a == b else 1
        max_run = max(max_run, run)
    if max_run >= 8:
        return True
    lines = [ln.strip() for ln in s.splitlines() if len(ln.strip()) > 3]
    if lines and Counter(lines).most_common(1)[0][1] >= 6:  # one line repeated
        return True
    return False


def _debug_dump_raw(raw: str) -> str | None:
    """Diagnostic-only: when SPEAKLOOP_DEBUG_LLM=1, save the raw LLM output (first
    8000 chars) under data/sessions/.debug-llm-raw/ so the operator can see what
    the model actually wrote. 8000 chars because parse failures often happen deep
    in the response. Never on by default; failures here are swallowed so
    debugging never breaks a session."""
    if os.environ.get("SPEAKLOOP_DEBUG_LLM") != "1":
        return None
    try:
        from speakloop.config import paths

        debug_dir = paths.sessions_dir() / ".debug-llm-raw"
        debug_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
        out = debug_dir / f"{stamp}.txt"
        out.write_text(raw[:8000], encoding="utf-8")
        return str(out)
    except Exception:  # noqa: BLE001 — diagnostics must never break the session
        return None


def _first_attempt_ordinal(pattern: GrammarPattern) -> int:
    return min((ev.get("attempt_ordinal", 99) for ev in pattern.evidence), default=99)


def _merge_key(p: GrammarPattern) -> str:
    """Identity for deduping: the catalog id when matched, else the normalized label."""
    return p.catalog_id or p.label.strip().lower()


def _dedupe(patterns: list[GrammarPattern]) -> list[GrammarPattern]:
    """Merge patterns sharing a canonical label (FR-004): sum ``occurrence_count``
    and union evidence (by attempt_ordinal+quote) so no repeated or near-duplicate
    restatement reaches the report. First occurrence keeps catalog metadata/order."""
    merged: dict[str, GrammarPattern] = {}
    order: list[str] = []
    for p in patterns:
        key = _merge_key(p)
        if key not in merged:
            merged[key] = p
            order.append(key)
            continue
        existing = merged[key]
        seen = {(e.get("attempt_ordinal"), e.get("quote")) for e in existing.evidence}
        for ev in p.evidence:
            sig = (ev.get("attempt_ordinal"), ev.get("quote"))
            if sig not in seen:
                existing.evidence.append(ev)
                seen.add(sig)
        existing.occurrence_count += p.occurrence_count
        if not existing.explanation and p.explanation:
            existing.explanation = p.explanation
    return [merged[k] for k in order]


def _verify_and_enrich(
    patterns: list[dict], transcripts: list[Transcript]
) -> list[GrammarPattern]:
    """Verify evidence, attach catalog metadata, suppress no-op fixes, and rank."""
    cat = catalog_mod.get_catalog()
    is_coherent = coherence.make_filter(transcripts)
    out: list[GrammarPattern] = []

    for p in patterns:
        if not isinstance(p, dict):
            continue  # json-repair may yield non-dict items (e.g. [1,2,3]); drop them
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

    # FR-004: merge near-duplicate patterns (same canonical label) before ranking.
    out = _dedupe(out)

    # FR-005: deterministic impact order; ties → more frequent, then earliest.
    out.sort(
        key=lambda p: (
            p.impact_rank if p.impact_rank is not None else OPEN_BUCKET_IMPACT_RANK,
            -p.occurrence_count,
            _first_attempt_ordinal(p),
        )
    )
    return out


def _generate_and_parse(
    transcripts: list[Transcript], llm: LLMEngine, max_tokens: int, *, retry: bool
) -> tuple[dict | None, str]:
    """One generate+parse pass. Returns (payload | None, raw_text). A ``<think>``
    leak is a hard misconfiguration error (not a retry case) and is raised here."""
    raw = llm.generate(
        _build_system_prompt(),
        _user_prompt(transcripts),
        max_tokens=max_tokens,
        retry=retry,
    )
    if "<think>" in raw:
        raise LLMEngineError("LLM response contains <think> leakage; engine misconfigured.")
    try:
        return _extract_json(raw), raw
    except (ValueError, json.JSONDecodeError):
        return None, raw


def analyze(
    transcripts: list[Transcript],
    llm: LLMEngine,
    *,
    max_tokens: int = 2048,
) -> list[GrammarPattern]:
    """Run the catalog-aware grammar analyzer; return verified, ranked findings.

    Generation config (temperature 0.7, repetition penalty, stop) is owned by the
    LLM wrapper (Principle V) — the call site no longer overrides it. On a parse
    failure OR a detected repetition loop, ONE bounded regenerate is attempted
    (FR-002, FR-003); on terminal failure the existing graceful path runs (caller
    records ``phase_c_error`` and renders the Phase-B report; the session never
    crashes)."""
    if not transcripts:
        return []

    payload, raw = _generate_and_parse(transcripts, llm, max_tokens, retry=False)
    if payload is None or _looks_like_repetition_loop(raw):
        # Bounded regenerate (at most one) — the wrapper raises repetition_penalty
        # and lowers temperature for this pass.
        payload_retry, raw_retry = _generate_and_parse(transcripts, llm, max_tokens, retry=True)
        if payload_retry is not None:
            payload, raw = payload_retry, raw_retry
        elif payload is None:
            dump_path = _debug_dump_raw(raw)
            suffix = f" (raw saved to {dump_path})" if dump_path else ""
            raise LLMEngineError(
                f"Could not parse LLM grammar response after one bounded regenerate{suffix}"
            )
        # else: the loop-flagged original parsed fine and the retry did not improve
        # parseability — keep the original payload rather than discard usable output.

    patterns_raw = payload.get("patterns") or []
    if not isinstance(patterns_raw, list):
        raise LLMEngineError("LLM response 'patterns' must be a list.")

    return _verify_and_enrich(patterns_raw, transcripts)
