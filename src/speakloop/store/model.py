"""Derived cross-session store dataclasses (010-interview-loop, P2a).

A single versioned JSON file (``~/.speakloop/store.json``) that is an internal
CACHE, fully rebuildable from session reports via ``store.rebuild`` — never a
source of truth (research R4). It holds three sections: the per-question SRS
schedule (P2b), the key-point cache keyed by question id + ideal-answer hash
(P3), and the cross-session grammar-pattern occurrence series (P2a).

This module is pure data + stdlib only (no engine imports, no I/O).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

STORE_VERSION = 1


@dataclass
class ScheduleEntry:
    """One question's spaced-repetition state (data-model §8).

    Foundational rebuild populates the observed fields (``last_grade``,
    ``last_practiced``, ``total_reviews``); the interval ladder / ``next_due`` /
    mastery computation is owned by ``srs.schedule`` and applied when P2 lands
    (the placeholders below keep the entry valid until then)."""

    question_id: str
    last_grade: str | None = None
    interval_days: int = 0
    next_due: str | None = None  # ISO date (YYYY-MM-DD)
    consecutive_strong: int = 0
    mastered: bool = False
    last_practiced: str | None = None  # ISO date
    total_reviews: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> ScheduleEntry:
        known = {f for f in cls.__dataclass_fields__}  # noqa: C416
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Store:
    """The whole derived store. Round-trips to/from a single JSON object."""

    store_version: int = STORE_VERSION
    rebuilt_at: str | None = None
    # question_id -> ScheduleEntry
    schedule: dict[str, ScheduleEntry] = field(default_factory=dict)
    # question_id -> ideal_answer_hash -> KeyPointSet dict (as stored in reports)
    key_points: dict[str, dict[str, dict]] = field(default_factory=dict)
    # pattern label -> chronological list of [iso_date, occurrence_count]
    patterns: dict[str, list[list]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "store_version": self.store_version,
            "rebuilt_at": self.rebuilt_at,
            "schedule": {qid: asdict(e) for qid, e in self.schedule.items()},
            "key_points": self.key_points,
            "patterns": self.patterns,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Store:
        if not isinstance(d, dict):
            return cls()
        schedule_raw = d.get("schedule") or {}
        schedule = {
            qid: ScheduleEntry.from_dict(e)
            for qid, e in schedule_raw.items()
            if isinstance(e, dict)
        }
        return cls(
            store_version=int(d.get("store_version", STORE_VERSION)),
            rebuilt_at=d.get("rebuilt_at"),
            schedule=schedule,
            key_points=d.get("key_points") or {},
            patterns=d.get("patterns") or {},
        )
