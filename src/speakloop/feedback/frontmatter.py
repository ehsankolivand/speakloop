"""Versioned YAML frontmatter serializer. Matches contracts/report-frontmatter.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import yaml

SCHEMA_VERSION = 1


@dataclass
class GrammarPattern:
    label: str
    occurrence_count: int
    evidence: list[dict] = field(default_factory=list)
    suggested_fix: str | None = None
    # --- Additive (002-post-session-debrief; schema_version stays 1) ----------
    # The "Because:" transfer reason (data-model §A.1). Catalog patterns inherit
    # it from the catalog transfer_reason; open-bucket patterns get an
    # LLM-supplied, non-empty value.
    explanation: str | None = None
    # 1 = highest impact on interview comprehensibility (FR-005). Resolved
    # deterministically at build time and persisted so render/read-aloud order is
    # reproducible from the file alone.
    impact_rank: int | None = None
    # The catalog entry id when this is a catalog match; None for open-bucket.
    catalog_id: str | None = None
    # Each evidence dict MAY additionally carry a "corrected" key (the "Better:"
    # line, data-model §A.2); evidence remains a list[dict] for back-compat.


@dataclass
class AttemptMetrics:
    words_total: int = 0
    speech_rate_wpm: float = 0.0
    filler_words_count: int = 0
    filler_density_per_100_words: float = 0.0
    pauses_count: int = 0
    mean_pause_ms: float = 0.0
    self_corrections_count: int = 0


@dataclass
class Attempt:
    ordinal: int
    time_budget_seconds: int
    actual_duration_seconds: float
    transcript: str = ""
    metrics: AttemptMetrics = field(default_factory=AttemptMetrics)


@dataclass
class Session:
    session_id: str
    started_at: datetime
    question_id: str
    question_text: str
    attempts: list[Attempt]
    grammar_patterns: list[GrammarPattern] = field(default_factory=list)
    generated_by_phase: Literal["A", "B", "C"] = "B"
    # --- Additive top-level keys (002-post-session-debrief) -------------------
    # Deterministic prose: what improved across the 4/3/2 rounds (data-model §A.3,
    # FR-008). Phase-B reports may carry a fluency-only narrative.
    cross_attempt_narrative: str | None = None
    # The single most important thing to fix next session (FR-008), chosen by the
    # most-impactful-wins rule across grammar + fluency. Rendered as the banner.
    top_priority: str | None = None


class _LiteralStr(str):
    """A str subclass that PyYAML renders as a block scalar (|)."""


def _literal_representer(dumper: yaml.Dumper, data: _LiteralStr):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


yaml.add_representer(_LiteralStr, _literal_representer)


def _attempt_to_dict(a: Attempt) -> dict:
    return {
        "ordinal": a.ordinal,
        "time_budget_seconds": a.time_budget_seconds,
        "actual_duration_seconds": round(a.actual_duration_seconds, 1),
        "metrics": {
            "words_total": int(a.metrics.words_total),
            "speech_rate_wpm": float(a.metrics.speech_rate_wpm),
            "filler_words_count": int(a.metrics.filler_words_count),
            "filler_density_per_100_words": float(a.metrics.filler_density_per_100_words),
            "pauses_count": int(a.metrics.pauses_count),
            "mean_pause_ms": float(a.metrics.mean_pause_ms),
            "self_corrections_count": int(a.metrics.self_corrections_count),
        },
    }


def _evidence_to_dict(ev: dict) -> dict:
    """Normalise one evidence item, preserving the additive `corrected` key."""
    out: dict = {
        "attempt_ordinal": int(ev.get("attempt_ordinal", 0)),
        "quote": str(ev.get("quote", "")),
    }
    corrected = ev.get("corrected")
    if corrected:
        out["corrected"] = str(corrected)
    return out


def _pattern_to_dict(p: GrammarPattern) -> dict:
    out: dict = {"label": p.label, "occurrence_count": int(p.occurrence_count)}
    # Additive fields are emitted only when present so Phase-B / pre-feature
    # readers see no change (schema_version stays 1).
    if p.impact_rank is not None:
        out["impact_rank"] = int(p.impact_rank)
    if p.catalog_id:
        out["catalog_id"] = p.catalog_id
    if p.explanation:
        out["explanation"] = p.explanation.strip()
    if p.evidence:
        out["evidence"] = [_evidence_to_dict(ev) for ev in p.evidence]
    if p.suggested_fix:
        out["suggested_fix"] = p.suggested_fix
    return out


def dump(session: Session) -> str:
    """Render a `---`-delimited YAML block. Key order is stable.

    `dump` is normalised (strings are stripped before block-scalar emission) so a
    `dump → parse → dump` round-trip is idempotent (see `parse`).
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session.session_id,
        "started_at": session.started_at.isoformat(),
        "question_id": session.question_id,
        "question": _LiteralStr(session.question_text.strip() + "\n"),
        "attempts": [_attempt_to_dict(a) for a in session.attempts],
        "grammar_patterns": [_pattern_to_dict(p) for p in session.grammar_patterns],
        "generated_by_phase": session.generated_by_phase,
    }
    # Additive top-level keys — emitted only when present so existing readers and
    # Phase-B reports are byte-identical to before (FR-031).
    if session.cross_attempt_narrative:
        payload["cross_attempt_narrative"] = _LiteralStr(session.cross_attempt_narrative.strip())
    if session.top_priority:
        payload["top_priority"] = _LiteralStr(session.top_priority.strip())
    body = yaml.dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{body}---\n"


def _frontmatter_dict(text: str) -> dict:
    """Extract the YAML frontmatter mapping from a report (or a bare block)."""
    stripped = text.lstrip()
    if stripped.startswith("---"):
        # `---\n<yaml>\n---\n<body>` → take the block between the first two `---`.
        parts = text.split("---\n", 2)
        if len(parts) >= 2:
            loaded = yaml.safe_load(parts[1])
            return loaded if isinstance(loaded, dict) else {}
    loaded = yaml.safe_load(text)
    return loaded if isinstance(loaded, dict) else {}


def _opt_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).rstrip("\n")
    return s or None


def _evidence_from_dict(ev: dict) -> dict:
    out: dict = {
        "attempt_ordinal": int(ev.get("attempt_ordinal", 0)),
        "quote": str(ev.get("quote", "")),
    }
    if ev.get("corrected"):
        out["corrected"] = str(ev["corrected"])
    return out


def _pattern_from_dict(d: dict) -> GrammarPattern:
    impact = d.get("impact_rank")
    return GrammarPattern(
        label=str(d.get("label", "")),
        occurrence_count=int(d.get("occurrence_count", 0)),
        evidence=[_evidence_from_dict(ev) for ev in (d.get("evidence") or [])],
        suggested_fix=d.get("suggested_fix") or None,
        explanation=_opt_str(d.get("explanation")),
        impact_rank=int(impact) if impact is not None else None,
        catalog_id=d.get("catalog_id") or None,
    )


def _attempt_from_dict(a: dict) -> Attempt:
    m = a.get("metrics") or {}
    return Attempt(
        ordinal=int(a.get("ordinal", 0)),
        time_budget_seconds=int(a.get("time_budget_seconds", 0)),
        actual_duration_seconds=float(a.get("actual_duration_seconds", 0.0)),
        # `transcript` is intentionally not serialised into frontmatter (it lives
        # in the report body), so it does not round-trip here.
        transcript="",
        metrics=AttemptMetrics(
            words_total=int(m.get("words_total", 0)),
            speech_rate_wpm=float(m.get("speech_rate_wpm", 0.0)),
            filler_words_count=int(m.get("filler_words_count", 0)),
            filler_density_per_100_words=float(m.get("filler_density_per_100_words", 0.0)),
            pauses_count=int(m.get("pauses_count", 0)),
            mean_pause_ms=float(m.get("mean_pause_ms", 0.0)),
            self_corrections_count=int(m.get("self_corrections_count", 0)),
        ),
    )


def parse(text: str) -> Session:
    """Inverse of `dump`: reconstruct a `Session` from report frontmatter.

    Unknown keys are ignored (forward-compat) and missing additive keys default
    to empty (a pre-feature report still parses). `transcript` is not stored in
    frontmatter, so attempts come back with empty transcript text; `dump → parse
    → dump` is therefore idempotent at the serialized level.
    """
    data = _frontmatter_dict(text)
    raw_started = data.get("started_at")
    if isinstance(raw_started, datetime):
        started_at = raw_started
    elif isinstance(raw_started, str):
        try:
            started_at = datetime.fromisoformat(raw_started)
        except ValueError:
            started_at = datetime.fromtimestamp(0)
    else:
        started_at = datetime.fromtimestamp(0)
    phase = data.get("generated_by_phase", "B")
    if phase not in ("A", "B", "C"):
        phase = "B"
    return Session(
        session_id=str(data.get("session_id", "")),
        started_at=started_at,
        question_id=str(data.get("question_id", "")),
        question_text=str(data.get("question", "")).rstrip("\n"),
        attempts=[_attempt_from_dict(a) for a in (data.get("attempts") or [])],
        grammar_patterns=[_pattern_from_dict(p) for p in (data.get("grammar_patterns") or [])],
        generated_by_phase=phase,
        cross_attempt_narrative=_opt_str(data.get("cross_attempt_narrative")),
        top_priority=_opt_str(data.get("top_priority")),
    )
