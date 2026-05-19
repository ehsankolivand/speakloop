"""Aggregate reports into a TrendsSummary."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from speakloop.trends.reader import Report

METRIC_KEYS = (
    "speech_rate_wpm",
    "filler_density_per_100_words",
    "pauses_count",
    "mean_pause_ms",
    "self_corrections_count",
)


@dataclass(frozen=True)
class PatternRankRow:
    label: str
    total_occurrences: int
    session_ids: list[str]


@dataclass
class TrendsSummary:
    total_sessions: int = 0
    date_range: tuple[date | None, date | None] = (None, None)
    metric_series: dict[str, list[tuple[date, float]]] = field(default_factory=dict)
    pattern_ranking: list[PatternRankRow] = field(default_factory=list)


def _attempt_three(report: Report) -> dict:
    for a in report.attempts:
        if int(a.get("ordinal", 0)) == 3:
            return a.get("metrics") or {}
    return {}


def aggregate(reports: list[Report], *, top_n: int = 10) -> TrendsSummary:
    if not reports:
        return TrendsSummary()

    dates = [r.started_at.date() for r in reports if r.started_at is not None]
    date_range = (min(dates), max(dates)) if dates else (None, None)

    metric_series: dict[str, list[tuple[date, float]]] = {k: [] for k in METRIC_KEYS}
    for r in reports:
        if r.started_at is None:
            continue
        m3 = _attempt_three(r)
        for k in METRIC_KEYS:
            v = m3.get(k)
            if v is None:
                continue
            metric_series[k].append((r.started_at.date(), float(v)))

    pattern_totals: dict[str, int] = defaultdict(int)
    pattern_sessions: dict[str, list[str]] = defaultdict(list)
    for r in reports:
        for p in r.grammar_patterns:
            label = (p.get("label") or "").strip()
            if not label:
                continue
            count = int(p.get("occurrence_count") or 0)
            pattern_totals[label] += count
            pattern_sessions[label].append(r.session_id)

    ranked = sorted(
        pattern_totals.items(),
        key=lambda kv: (-kv[1], kv[0]),  # desc by count, asc by label for ties
    )[:top_n]
    pattern_ranking = [
        PatternRankRow(label=label, total_occurrences=total, session_ids=pattern_sessions[label])
        for label, total in ranked
    ]

    return TrendsSummary(
        total_sessions=len(reports),
        date_range=date_range,
        metric_series=metric_series,
        pattern_ranking=pattern_ranking,
    )
