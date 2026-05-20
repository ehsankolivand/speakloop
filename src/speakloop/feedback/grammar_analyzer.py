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
from datetime import UTC, datetime

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
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
_SINGLE_QUOTED_KEY_RE = re.compile(r"([{,]\s*)'([^'\\]*)'(\s*:)")
_BARE_KEY_RE = re.compile(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)")
_SINGLE_QUOTED_VALUE_RE = re.compile(r"([:\[,]\s*)'((?:[^'\\]|\\.)*)'")
# A stray junk token (1-4 alnum chars) that some reasoning models leak right
# before a quoted key, e.g. `1,\n    a "quote": ...`. Conservative: it must sit
# between a separator (`{`, `,`, or newline) and a *quoted key* (`"..."` then
# `:`), so a legitimate unquoted key (`token:`) is never touched.
_JUNK_TOKEN_BEFORE_KEY_RE = re.compile(r'([\n,{]\s*)[a-z0-9]{1,4}\s+("[^"]*"\s*:)')


def _strip_code_fences(raw: str) -> str:
    """Remove a surrounding markdown code fence (```json ... ``` or ``` ... ```)."""
    m = _FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()
    # Fence markers without a clean closing pair: drop stray ``` lines.
    return re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()


def _repair_json(s: str) -> str:
    """Best-effort repair of the common LLM bad-JSON cases (research: Qwen emits
    single-quoted/trailing-comma JSON). Keys are fixed before values so already
    double-quoted keys are never touched."""
    s = _TRAILING_COMMA_RE.sub(r"\1", s)  # drop trailing commas before } or ]
    s = _JUNK_TOKEN_BEFORE_KEY_RE.sub(r"\1\2", s)  # `, a "key":` -> `, "key":`
    s = _SINGLE_QUOTED_KEY_RE.sub(r'\1"\2"\3', s)  # 'key': -> "key":
    s = _BARE_KEY_RE.sub(r'\1"\2"\3', s)  # key: -> "key":
    s = _SINGLE_QUOTED_VALUE_RE.sub(r'\1"\2"', s)  # : 'val' / ['val' -> : "val"
    return s


def _loads_lenient(s: str) -> dict:
    """Parse JSON, falling back to a repair pass (and json5 if installed). If all
    fail, re-raise the ORIGINAL json error so phase_c_error shows the real issue."""
    try:
        return json.loads(s)
    except json.JSONDecodeError as original:
        try:
            return json.loads(_repair_json(s))
        except json.JSONDecodeError:
            pass
        try:
            import json5  # optional; not in the closed dep set, used only if present

            return json5.loads(s)
        except ImportError:
            pass
        except Exception:  # noqa: BLE001 — json5 parse failure: fall through to original
            pass
        raise original


def _extract_json(raw: str) -> dict:
    """Pull the first JSON object out of the LLM response, tolerating markdown
    fences and the common single-quote / trailing-comma emissions."""
    raw = _strip_code_fences(raw.strip())
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract JSON from LLM response: {raw[:200]}")
    return _loads_lenient(match.group(0))


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
        dump_path = _debug_dump_raw(raw)
        suffix = f" (raw saved to {dump_path})" if dump_path else ""
        raise LLMEngineError(f"Could not parse LLM grammar response: {e}{suffix}") from e

    patterns_raw = payload.get("patterns") or []
    if not isinstance(patterns_raw, list):
        raise LLMEngineError("LLM response 'patterns' must be a list.")

    return _verify_and_enrich(patterns_raw, transcripts)
