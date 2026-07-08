"""T027 (018, US2) — abbreviation-aware sentence splitting of ideal answers."""

from __future__ import annotations

import pytest

from speakloop.shadowing.split import split_sentences

pytestmark = pytest.mark.unit


def test_basic_multi_sentence():
    text = "The window is detached. The view hierarchy is disconnected. Observers receive ON_DESTROY."
    assert split_sentences(text) == [
        "The window is detached.",
        "The view hierarchy is disconnected.",
        "Observers receive ON_DESTROY.",
    ]


def test_paragraph_breaks_are_hard_boundaries():
    text = "First paragraph sentence.\n\nSecond paragraph sentence."
    assert split_sentences(text) == ["First paragraph sentence.", "Second paragraph sentence."]


def test_commas_and_colons_do_not_split():
    text = ("On the old instance, the callbacks fire in this order: onPause, then onStop, "
            "then onSaveInstanceState with a Bundle, then onDestroy.")
    assert split_sentences(text) == [text]


def test_decimal_is_not_split():
    assert split_sentences("The value was 3.14 exactly. Then it changed.") == [
        "The value was 3.14 exactly.",
        "Then it changed.",
    ]


def test_version_token_is_not_split():
    out = split_sentences("We shipped v2.0 last week. It works.")
    assert out == ["We shipped v2.0 last week.", "It works."]


def test_dotted_identifier_is_not_split():
    assert split_sentences("Call System.out here. Then return.") == [
        "Call System.out here.",
        "Then return.",
    ]


def test_abbreviation_is_not_split():
    assert split_sentences("Use a cache, e.g. Redis, for reads. It helps.") == [
        "Use a cache, e.g. Redis, for reads.",
        "It helps.",
    ]


def test_api_version_period_is_a_real_boundary():
    # "API 28" itself has no period; the period after it legitimately ends the sentence
    assert split_sentences("This is the API 28 behavior. On API 27 it differed.") == [
        "This is the API 28 behavior.",
        "On API 27 it differed.",
    ]


def test_single_sentence_answer_yields_one_item():
    text = "The Activity Java object becomes unreachable from the framework."
    assert split_sentences(text) == [text]


def test_real_ideal_answer_paragraph_splits_as_expected():
    text = (
        "ActivityThread releases its reference in ActivityClientRecord. The window is detached. "
        "The view hierarchy is disconnected. The instance becomes eligible for garbage collection."
    )
    assert split_sentences(text) == [
        "ActivityThread releases its reference in ActivityClientRecord.",
        "The window is detached.",
        "The view hierarchy is disconnected.",
        "The instance becomes eligible for garbage collection.",
    ]
