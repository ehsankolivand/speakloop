"""Rebuild the derived store from session reports (010-interview-loop, P2a).

The store is fully rebuildable from ``data/sessions/*.md`` — this is what makes it
a cache rather than a source of truth (research R4). Folds, per report:

- ``patterns[label]``  ← chronological occurrence-count series from each report's
  grammar patterns (follow-up grammar, if present, is tagged in the report and
  still counts).
- ``key_points[qid][hash]``  ← the key-point set recorded in the LATEST report for
  that question + ideal-answer hash (P3).
- ``schedule[qid]``  ← the observed grade history (last_grade / last_practiced /
  total_reviews). The interval-ladder / next-due / mastery computation is owned by
  ``srs.schedule`` and applied when P2 lands; until then those fields stay at their
  placeholder defaults (see store.model.ScheduleEntry).

Pure stdlib + frontmatter parsing; no engine imports.
"""

from __future__ import annotations

from pathlib import Path

from speakloop.feedback import frontmatter
from speakloop.store.model import STORE_VERSION, ScheduleEntry, Store


def _iter_sessions(sessions_dir: Path):
    """Yield parsed Sessions in chronological order, skipping unparseable files."""
    parsed = []
    for path in sorted(Path(sessions_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            session = frontmatter.parse(text)
        except Exception:
            continue  # malformed / non-speakloop fixture → skip (cache is rebuildable)
        if not session.session_id:
            continue
        parsed.append(session)
    parsed.sort(key=lambda s: s.started_at)
    return parsed


def rebuild(sessions_dir: Path, *, rebuilt_at: str | None = None) -> Store:
    """Fold every session report into a fresh Store (deterministic)."""
    store = Store(store_version=STORE_VERSION, rebuilt_at=rebuilt_at)

    for session in _iter_sessions(sessions_dir):
        iso_date = session.started_at.date().isoformat()
        qid = session.question_id

        # --- patterns (P2a) ---------------------------------------------------
        for pattern in session.grammar_patterns:
            label = (pattern.label or "").strip()
            if not label:
                continue
            store.patterns.setdefault(label, []).append([iso_date, int(pattern.occurrence_count)])

        # --- key points (P3) — latest report per (question, ideal-answer hash) -
        kp = session.key_points
        if isinstance(kp, dict) and kp.get("ideal_answer_hash"):
            khash = str(kp["ideal_answer_hash"])
            store.key_points.setdefault(qid, {})[khash] = kp

        # --- schedule (P2b) — observed grade history; srs completes this in P2 -
        if qid:
            entry = store.schedule.get(qid) or ScheduleEntry(question_id=qid)
            entry.total_reviews += 1
            entry.last_practiced = iso_date
            entry.next_due = iso_date  # placeholder until srs.schedule lands (P2)
            if session.answer_grade:
                entry.last_grade = session.answer_grade
            store.schedule[qid] = entry

    # patterns are appended in chronological order already (sessions sorted), but
    # sort defensively so the series is always chronological.
    for series in store.patterns.values():
        series.sort(key=lambda pair: pair[0])

    return store
