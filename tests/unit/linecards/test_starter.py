"""T016 (018, US1) — the bundled starter rescue-line cards."""

from __future__ import annotations

import pytest

from speakloop.linecards.starter import load_starter_cards

pytestmark = pytest.mark.unit


def test_at_least_eight_starter_cards():
    assert len(load_starter_cards()) >= 8  # FR-013 / SC-006


def test_each_starter_card_is_well_formed_and_clozable():
    for card in load_starter_cards():
        assert card.source == "starter"
        assert card.card_id.startswith("starter:")
        assert card.corrected.strip()
        assert card.cloze.strip(), f"{card.card_id} has no cloze span"
        # the exporter wraps `cloze` inside `corrected`, so it must be a substring
        assert card.cloze in card.corrected, f"{card.card_id} cloze not a substring of text"
        assert card.quote == "" and card.question_id == ""


def test_starter_cards_are_english_ascii():
    for card in load_starter_cards():
        assert card.corrected.isascii(), f"{card.card_id} is not plain English/ASCII"


def test_missing_file_yields_empty(tmp_path):
    assert load_starter_cards(tmp_path / "nope.yaml") == []
