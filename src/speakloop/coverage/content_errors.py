"""Content-error validation (010-interview-loop, P3).

Content errors come from the single coverage call (``scoring.score_coverage``).
This module validates/normalizes them: a content error is a mutually-exclusive
contradiction with both the learner's claim and the ideal claim present (FR-021);
omissions / extra-but-correct facts are dropped. Kept separate from grammar errors.
Pure logic — no LLM/engine.
"""

from __future__ import annotations

import contextlib


def validate_content_errors(raw) -> list[dict]:
    """Return only well-formed content errors (both claims present, distinct)."""
    out: list[dict] = []
    for e in raw or []:
        if not isinstance(e, dict):
            continue
        learner = str(e.get("learner_claim", "")).strip()
        ideal = str(e.get("ideal_claim", "")).strip()
        if not learner or not ideal or learner.lower() == ideal.lower():
            continue  # not a mutually-exclusive contradiction
        item = {"learner_claim": learner, "ideal_claim": ideal}
        # `attempt_ordinal`/`key_point_id` are optional LLM-supplied enrichment. A
        # non-numeric value ("attempt 3", "n/a") must not crash the whole coverage pass
        # (mirrors grammar_analyzer._verify_and_enrich): drop just the malformed field —
        # the mutually-exclusive contradiction itself is still a valid finding.
        if e.get("attempt_ordinal") is not None:
            with contextlib.suppress(TypeError, ValueError):
                item["attempt_ordinal"] = int(e["attempt_ordinal"])
        if e.get("key_point_id") is not None:
            with contextlib.suppress(TypeError, ValueError):
                item["key_point_id"] = int(e["key_point_id"])
        out.append(item)
    return out
