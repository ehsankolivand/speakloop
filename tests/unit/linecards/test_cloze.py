"""T014 (018, US1) — Anki cloze derivation (word-diff) + export line format."""

from __future__ import annotations

import pytest

from speakloop.linecards import cards
from speakloop.linecards.cloze import anki_line, cloze_from_correction, to_anki

pytestmark = pytest.mark.unit


def test_article_insertion_clozes_the_inserted_word():
    assert cloze_from_correction("new instance of it", "a new instance of it") == "{{c1::a}} new instance of it"


def test_verb_change_clozes_the_changed_word():
    assert cloze_from_correction("system create", "system creates") == "system {{c1::creates}}"


def test_replacement_clozes_only_the_replaced_token():
    assert cloze_from_correction("i has", "i have") == "i {{c1::have}}"


def test_multiple_insertions_each_get_a_cloze():
    assert cloze_from_correction("to top", "to the top of") == "to {{c1::the}} top {{c1::of}}"


def test_empty_quote_falls_back_to_whole_phrase():
    assert cloze_from_correction("", "let me walk you through") == "{{c1::let me walk you through}}"


def test_pure_deletion_falls_back_to_whole_phrase():
    # nothing new on the corrected side -> cloze the whole corrected line so the card is usable
    assert cloze_from_correction("i really have", "i have") == "{{c1::i have}}"


def test_anki_line_report_card_appends_rule_hint():
    card = cards.LineCard("id", "system creates", "system create", "third person singular", "q", "report")
    assert anki_line(card) == "system {{c1::creates}} (third person singular)"


def test_anki_line_starter_card_wraps_its_explicit_span():
    card = cards.LineCard(
        "starter:x", "Let me walk you through my approach.", "", "signpost first", "", "starter",
        cloze="walk you through",
    )
    assert anki_line(card) == "Let me {{c1::walk you through}} my approach. (signpost first)"


def test_to_anki_is_one_card_per_line_all_with_cloze():
    deck = cards.LineCard("a", "a new instance", "new instance", "", "q", "report")
    starter = cards.LineCard("starter:s", "In a nutshell, we cache it.", "", "", "", "starter", cloze="In a nutshell")
    out = to_anki([deck, starter])
    lines = out.splitlines()
    assert len(lines) == 2
    assert all("{{c1::" in line for line in lines)
