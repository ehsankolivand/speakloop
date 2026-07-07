"""Aggregate reports into a TrendsSummary."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from speakloop.trends.reader import Report

_MIN_DT = datetime.min

METRIC_KEYS = (
    "speech_rate_wpm",
    "filler_density_per_100_words",
    "pauses_count",
    "mean_pause_ms",
    "self_corrections_count",
)

# Human labels + direction for the trends dashboard (IMP-042). `METRIC_KEYS` stays the single
# source for ordering; these only affect display. `higher_is_better` drives the Δ annotation:
# rising WPM is the desired trajectory, but more fillers/pauses/self-corrections is a regression.
METRIC_LABELS = {
    "speech_rate_wpm": "Speech rate (WPM)",
    "filler_density_per_100_words": "Filler density (/100 words)",
    "pauses_count": "Pauses",
    "mean_pause_ms": "Mean pause (ms)",
    "self_corrections_count": "Self-corrections",
}
METRIC_HIGHER_IS_BETTER = {
    "speech_rate_wpm": True,
    "filler_density_per_100_words": False,
    "pauses_count": False,
    "mean_pause_ms": False,
    "self_corrections_count": False,
}


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
    # 010 P2a: per-pattern occurrence series across sessions (chronological), for
    # the "stats" view (FR-009). label -> [(date, count), ...].
    pattern_series: dict[str, list[tuple[date, int]]] = field(default_factory=dict)


def format_series(series: list[tuple[date, int]], *, window: int = 3) -> str:
    """Render the last ``window`` occurrence counts as e.g. "10 → 4 → 1" (FR-008).

    A single data point renders as a bare number (no arrow), matching the
    single-data-point edge case."""
    counts = [int(c) for _, c in series[-window:]]
    return " → ".join(str(c) for c in counts)


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
    pattern_series: dict[str, list[tuple[date, int]]] = defaultdict(list)
    for r in sorted(reports, key=lambda rr: rr.started_at or _MIN_DT):
        for p in r.grammar_patterns:
            label = (p.get("label") or "").strip()
            if not label:
                continue
            count = int(p.get("occurrence_count") or 0)
            pattern_totals[label] += count
            pattern_sessions[label].append(r.session_id)
            if r.started_at is not None:
                pattern_series[label].append((r.started_at.date(), count))

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
        pattern_series=dict(pattern_series),
    )
