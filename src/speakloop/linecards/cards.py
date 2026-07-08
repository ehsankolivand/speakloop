"""Rescue-line card model + derivation from session reports (018, US1).

A card is one of the learner's own corrected lines: the "Better:" text they should be able
to say, paired with the "You said" quote and the rule that explains the fix. Cards are derived
DETERMINISTICALLY from the structured grammar evidence already in `data/sessions/*.md`
(`grammar_patterns[].evidence[]{quote, corrected}`), so the deck is fully rebuildable from
reports (the store stays a cache). Pure logic — the only I/O is reading report files.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from speakloop.feedback import frontmatter

# The SRS scheduling fields persisted per card (mirror the observable ScheduleEntry fields,
# keyed by card_id instead of question_id). Placeholder values = a never-reviewed card.
_SRS_FIELDS: tuple[str, ...] = (
    "last_grade",
    "interval_days",
    "next_due",
    "consecutive_strong",
    "mastered",
    "last_practiced",
    "total_reviews",
)
_CONTENT_FIELDS: tuple[str, ...] = ("corrected", "quote", "rule", "question_id", "source", "cloze")


@dataclass(frozen=True)
class LineCard:
    """One drillable corrected line. Content is rebuildable from reports; SRS state lives
    alongside it in the store (see `deck.advance_card`)."""

    card_id: str
    corrected: str  # the target line the learner hears/says ("Better:")
    quote: str  # the learner's original ("You said"); "" for starter cards
    rule: str  # short hint (pattern explanation or label); "" if none
    question_id: str  # source question id; "" for starter cards
    source: str  # "report" | "starter"
    cloze: str = ""  # explicit cloze span (starter cards); "" -> exporter diffs quote->corrected


def card_id(question_id: str, quote: str, corrected: str) -> str:
    """Stable id for a derived card. The same correction seen in multiple reports collapses
    to one card (FR-012). Unit-separator-joined so distinct fields can't collide."""
    raw = f"{question_id}\x1f{quote}\x1f{corrected}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _card_from_evidence(question_id: str, ev: dict, *, rule: str) -> LineCard | None:
    """Build a card from one evidence item, or None for a no-op/absent correction (FR-011)."""
    quote = str(ev.get("quote") or "").strip()
    corrected = str(ev.get("corrected") or "").strip()
    if not corrected or corrected == quote:
        return None
    return LineCard(
        card_id=card_id(question_id, quote, corrected),
        corrected=corrected,
        quote=quote,
        rule=rule,
        question_id=question_id,
        source="report",
    )


def cards_from_session(session: frontmatter.Session) -> list[LineCard]:
    """Every rescue-line card derivable from ONE parsed report (in report order, no dedupe).

    Shared by `derive_cards` (deck runtime) and `store.rebuild` (cache fold) so the derivation
    rule lives in exactly one place."""
    qid = session.question_id
    out: list[LineCard] = []
    for pattern in session.grammar_patterns:
        rule = (pattern.explanation or pattern.label or "").strip()
        for ev in pattern.evidence:
            card = _card_from_evidence(qid, ev, rule=rule)
            if card is not None:
                out.append(card)
    return out


def derive_cards(reports_dir: Path) -> list[LineCard]:
    """Derive rescue-line cards from every session report under ``reports_dir``.

    Mirrors `trends.reader`: flat non-recursive glob, per-file tolerance (a malformed or
    non-SpeakLoop file is skipped, never aborting the batch), dedupe by `card_id` (stable
    identity). Deterministic and offline."""
    seen: dict[str, LineCard] = {}
    for path in sorted(Path(reports_dir).glob("*.md")):
        try:
            session = frontmatter.parse(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — unreadable / non-UTF8 / malformed → skip (cache is rebuildable)
            continue
        if not session.session_id:
            continue
        for card in cards_from_session(session):
            seen.setdefault(card.card_id, card)
    return list(seen.values())


def new_state() -> dict:
    """Placeholder SRS state for a never-reviewed card (also what a `rebuild` restores)."""
    return {
        "last_grade": None,
        "interval_days": 0,
        "next_due": None,
        "consecutive_strong": 0,
        "mastered": False,
        "last_practiced": None,
        "total_reviews": 0,
    }


def content_dict(card: LineCard) -> dict:
    """The rebuildable content half of a stored card row."""
    return {
        "corrected": card.corrected,
        "quote": card.quote,
        "rule": card.rule,
        "question_id": card.question_id,
        "source": card.source,
        "cloze": card.cloze,
    }


def card_from_row(card_id_: str, row: dict) -> LineCard:
    """Reconstruct a LineCard from a stored `line_cards` row (content fields only)."""
    return LineCard(
        card_id=card_id_,
        corrected=str(row.get("corrected") or ""),
        quote=str(row.get("quote") or ""),
        rule=str(row.get("rule") or ""),
        question_id=str(row.get("question_id") or ""),
        source=str(row.get("source") or "report"),
        cloze=str(row.get("cloze") or ""),
    )


def merge_cards(
    derived: list[LineCard], starter: list[LineCard], stored: dict[str, dict]
) -> dict[str, dict]:
    """Return the full deck as a `card_id -> {content + SRS state}` map.

    Content comes from freshly-derived + starter cards (bundled content is always available);
    SRS scheduling state is kept from ``stored`` where present, else the placeholder. New cards
    are added; existing review history is preserved; a stored card whose content is no longer
    derivable is kept as long as it still carries content (nothing is silently dropped)."""
    content_by_id: dict[str, LineCard] = {}
    for card in [*derived, *starter]:
        content_by_id.setdefault(card.card_id, card)

    out: dict[str, dict] = {}
    for cid in set(content_by_id) | set(stored):
        prev = stored.get(cid) or {}
        found = content_by_id.get(cid)
        if found is not None:
            content = content_dict(found)
        elif prev.get("corrected"):
            content = {k: prev.get(k, "") for k in _CONTENT_FIELDS}
        else:
            continue  # no content anywhere -> skip
        state = {k: prev.get(k, new_state()[k]) for k in _SRS_FIELDS}
        out[cid] = {**content, **state}
    return out
