"""Shared LLM-JSON recovery ladder (llm-calls.md O8; feedback/CLAUDE.md O4).

`extract_json` is the single JSON-recovery primitive reused across analysis modules
(grammar, triage mishearing/consistency, warm-up drill; coverage/keypoints/followups reach
it via `grammar_analyzer.generate_json`). Kept in its own module — a PUBLIC symbol, not a
private `grammar_analyzer._extract_json` cross-import — so the contract is explicit and a
future `grammar_analyzer` refactor can't silently break the other callers (IMP-034).
"""

from __future__ import annotations

import json
import re

import json_repair

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", flags=re.DOTALL | re.IGNORECASE)


def strip_code_fences(raw: str) -> str:
    """Remove a surrounding markdown code fence (```json ... ``` or ``` ... ```)."""
    m = _FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()
    # Fence markers without a clean closing pair: drop stray ``` lines.
    return re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()


def extract_json(raw: str) -> dict:
    """Recover a JSON object from an LLM response (recovery ladder —
    contracts/grammar-output-schema.md §C; research Decision 3):

    1. strict ``json.loads`` of the fence-stripped text,
    2. strict parse of the first ``{...}`` region (tolerates surrounding prose),
    3. ``json_repair`` on the full text — recovers single/bare-quoted keys,
       trailing commas, junk-token-before-key, AND truncated/unclosed objects
       (the case the old hand-rolled regex repair could not handle),
    4. ``json_repair`` on just the ``{...}`` region as a last resort.

    Returns a dict. Raises ``ValueError`` only when nothing yields a JSON object (the caller
    may bounded-regenerate once, else fall back gracefully)."""
    raw = strip_code_fences(raw.strip())
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
