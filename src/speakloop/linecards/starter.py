"""Load the bundled starter rescue-line cards (018, US1, FR-013).

Seeds the deck with high-value interview discourse chunks so a learner with no prior
corrections still has cards to drill. English-only bundled content; each entry carries an
explicit cloze span (there is no "You said" quote to diff). Read-only.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from speakloop.linecards.cards import LineCard

_STARTER_PATH = Path(__file__).parent / "starter_cards.yaml"


def load_starter_cards(path: Path | None = None) -> list[LineCard]:
    """Return the bundled starter cards as `LineCard`s (source="starter"). Malformed or
    incomplete entries are skipped; a missing/unreadable file yields an empty list."""
    p = path or _STARTER_PATH
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(data, dict):
        return []

    cards: list[LineCard] = []
    for entry in data.get("cards") or []:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("slug") or "").strip()
        text = str(entry.get("text") or "").strip()
        if not (slug and text):
            continue
        cards.append(
            LineCard(
                card_id=f"starter:{slug}",
                corrected=text,
                quote="",
                rule=str(entry.get("rule") or "").strip(),
                question_id="",
                source="starter",
                cloze=str(entry.get("cloze") or "").strip(),
            )
        )
    return cards
