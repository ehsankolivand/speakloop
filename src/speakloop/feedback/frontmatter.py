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


def _pattern_to_dict(p: GrammarPattern) -> dict:
    out = {"label": p.label, "occurrence_count": int(p.occurrence_count)}
    if p.evidence:
        out["evidence"] = list(p.evidence)
    if p.suggested_fix:
        out["suggested_fix"] = p.suggested_fix
    return out


def dump(session: Session) -> str:
    """Render a `---`-delimited YAML block. Key order is stable."""
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
    body = yaml.dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{body}---\n"
