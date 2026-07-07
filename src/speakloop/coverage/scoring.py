"""Coverage scoring (010-interview-loop, P3).

One LLM call over all three attempts (contract C3) returns per-attempt covered/
partial/missed for each key point + the content errors. This module makes the call
and turns the raw JSON into per-attempt coverage records with a deterministic
aggregate = (covered + 0.5·partial) / N; content-error validation lives in
``content_errors.py``. Reuses the injected ``LLMEngine`` + JSON recovery ladder.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from speakloop.asr import Transcript
from speakloop.feedback.grammar_analyzer import _extract_json
from speakloop.llm import LLMEngine, LLMEngineError

_COVERAGE_MAX_TOKENS = 1024
_COVERAGE_TEMPERATURE = 0.2

_VALID_STATES = {"covered", "partial", "missed"}


@dataclass
class CoverageResult:
    attempt_records: list[dict] = field(default_factory=list)  # frontmatter coverage records
    content_errors: list[dict] = field(default_factory=list)
    final_aggregate: float | None = None  # last attempt's aggregate (drives the grade)


def _aggregate(per_point: list[dict]) -> float:
    if not per_point:
        return 0.0
    covered = sum(1 for p in per_point if p["state"] == "covered")
    partial = sum(1 for p in per_point if p["state"] == "partial")
    return round((covered + 0.5 * partial) / len(per_point), 3)


def _coverage_records(raw: dict, key_points: list[dict], *, version: int) -> list[dict]:
    """Build per-attempt frontmatter coverage records, defaulting missing ids to missed."""
    point_ids = [int(p["id"]) for p in key_points]
    records: list[dict] = []
    for att in raw.get("attempts") or []:
        if not isinstance(att, dict):
            continue
        # `ordinal`/`id` come straight from the model; a non-numeric value must not crash
        # the whole coverage pass (which would discard every valid attempt too and flag the
        # report pending). Skip just the malformed attempt / coverage entry instead.
        try:
            ordinal = int(att.get("ordinal", 0))
        except (TypeError, ValueError):
            continue
        states = {}
        for c in att.get("coverage") or []:
            if isinstance(c, dict) and "id" in c:
                try:
                    cid = int(c["id"])
                except (TypeError, ValueError):
                    continue  # skip this coverage entry; the point defaults to "missed"
                # Lowercase before the membership test (mirroring the sibling LLM-output
                # handlers) so a capitalized-but-valid state ("Covered"/"Partial") is not
                # silently downgraded to "missed" and dropped from the aggregate.
                state = str(c.get("state", "")).strip().lower()
                states[cid] = state if state in _VALID_STATES else "missed"
        per_point = [{"id": pid, "state": states.get(pid, "missed")} for pid in point_ids]
        records.append(
            {
                "attempt_ordinal": ordinal,
                "key_points_version": version,
                "aggregate": _aggregate(per_point),
                "per_point": per_point,
            }
        )
    records.sort(key=lambda r: r["attempt_ordinal"])
    return records


def score_coverage(
    key_points: list[dict],
    transcripts: list[Transcript],
    ideal_answer: str,
    llm: LLMEngine,
    *,
    system_prompt: str,
    version: int,
) -> CoverageResult:
    """Score coverage + content errors over all attempts (one call). Raises
    ``LLMEngineError`` on empty/failed response (coordinator degrades gracefully)."""
    from speakloop.coverage.content_errors import validate_content_errors

    kp_block = "\n".join(f'{p["id"]}. {p["text"]}' for p in key_points)
    attempts_block = "\n".join(
        f"Attempt {i}: {t.text.strip()}" for i, t in enumerate(transcripts, start=1)
    )
    user_prompt = (
        f"Key points:\n{kp_block}\n\n"
        f"Reference answer:\n{ideal_answer.strip()}\n\n"
        f"Candidate attempts:\n{attempts_block}"
    )
    out = llm.generate(
        system_prompt, user_prompt, max_tokens=_COVERAGE_MAX_TOKENS, temperature=_COVERAGE_TEMPERATURE
    )
    if not out or not out.strip():
        raise LLMEngineError("Coverage scoring returned an empty response.")
    raw = _extract_json(out)

    records = _coverage_records(raw, key_points, version=version)
    content_errors = validate_content_errors(raw.get("content_errors"))
    final_aggregate = records[-1]["aggregate"] if records else None
    return CoverageResult(
        attempt_records=records, content_errors=content_errors, final_aggregate=final_aggregate
    )
