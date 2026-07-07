"""Generated-artifact consistency check (010-interview-loop, P4).

Before the report is written, every generated learning artifact (improved answer,
flashcards, drill sentences) is checked for factual consistency against the ideal
answer (FR-027). A contradiction is corrected (the model returns a fixed artifact)
or the artifact is dropped. If the check itself cannot run (``LLMEngineError`` or
unparseable output), the artifact is WITHHELD rather than shown unchecked — wrong
feedback is worse than none (spec P4 rationale / contract C5).

Reuses the injected ``LLMEngine`` (no engine import) and ``_extract_json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from speakloop.feedback.json_recovery import extract_json
from speakloop.llm import LLMEngine, LLMEngineError

_CONSISTENCY_MAX_TOKENS = 1024
_CONSISTENCY_TEMPERATURE = 0.2


@dataclass
class ConsistencyVerdict:
    """Outcome of one artifact consistency check."""

    consistent: bool
    contradictions: list[dict] = field(default_factory=list)
    corrected: str | None = None  # a fully-corrected artifact, when the model fixed it
    withheld: bool = False  # the check could not run → drop the artifact


def check_artifact(
    artifact: str,
    ideal_answer: str,
    llm: LLMEngine,
    *,
    system_prompt: str,
) -> ConsistencyVerdict:
    """Check ``artifact`` against ``ideal_answer``. Withhold on any failure."""
    user_prompt = (
        f"Reference answer:\n{(ideal_answer or '').strip()}\n\n"
        f"Generated artifact:\n{(artifact or '').strip()}"
    )
    try:
        raw = llm.generate(
            system_prompt,
            user_prompt,
            max_tokens=_CONSISTENCY_MAX_TOKENS,
            temperature=_CONSISTENCY_TEMPERATURE,
        )
        data = extract_json(raw)
    except (LLMEngineError, ValueError):
        return ConsistencyVerdict(consistent=False, withheld=True)

    consistent = bool(data.get("consistent"))
    contradictions = [c for c in (data.get("contradictions") or []) if isinstance(c, dict)]
    corrected = data.get("corrected")
    corrected = str(corrected).strip() if corrected else None
    return ConsistencyVerdict(
        consistent=consistent,
        contradictions=contradictions,
        corrected=corrected,
    )


def resolve(artifact: str, verdict: ConsistencyVerdict) -> str | None:
    """Apply a verdict: keep the artifact, replace it with the correction, or drop.

    Returns the text to write, or ``None`` when the artifact must be withheld
    (a contradiction with no safe correction, or a check that could not run).
    Guarantees no contradiction survives to the report (SC-004)."""
    if verdict.consistent and not verdict.withheld:
        return artifact
    if verdict.corrected:
        return verdict.corrected
    return None
