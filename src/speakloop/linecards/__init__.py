"""Rescue-lines deck — Mode A pure logic (018-self-practice-modes).

Derives spaced-repetition flashcards from the learner's own corrected lines in past session
reports (`grammar_patterns[].evidence[]{quote, corrected}`) plus a bundled starter set,
schedules them on the shared SRS ladder (`srs.schedule.advance`), and exports them as offline
Anki cloze cards. Pure logic only — no engine import; the only I/O is reading report files and
the bundled starter YAML.
"""

from __future__ import annotations

from speakloop.linecards.cards import (
    LineCard,
    card_from_row,
    card_id,
    content_dict,
    derive_cards,
    merge_cards,
    new_state,
)
from speakloop.linecards.cloze import anki_line, cloze_from_correction, to_anki
from speakloop.linecards.deck import advance_card, any_due, select_due
from speakloop.linecards.starter import load_starter_cards

__all__ = [
    "LineCard",
    "card_id",
    "derive_cards",
    "merge_cards",
    "new_state",
    "content_dict",
    "card_from_row",
    "cloze_from_correction",
    "anki_line",
    "to_anki",
    "advance_card",
    "select_due",
    "any_due",
    "load_starter_cards",
]
