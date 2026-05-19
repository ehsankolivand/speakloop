"""T056 — self-corrections deterministic heuristic (FR-012c)."""

from __future__ import annotations

import sys

import pytest

from speakloop.metrics import self_corrections

pytestmark = pytest.mark.unit


def test_verbatim_repeat_pair_counts_once():
    assert self_corrections.verbatim_repeat_count("the the") == 1
    assert self_corrections.verbatim_repeat_count("I I went") == 1


def test_no_double_count_overlapping_triples():
    assert self_corrections.verbatim_repeat_count("the the the") == 1


def test_repair_markers_counted():
    text = "I mean, sorry, let me rephrase. actually no, what I meant. wait."
    assert self_corrections.repair_marker_count(text) == 6


def test_combined_count():
    text = "the the cat, I mean the dog."
    # 1 repeat + 1 repair marker
    assert self_corrections.self_corrections_count(text) == 2


def test_llm_not_imported():
    # speakloop.llm may have been imported elsewhere, but self_corrections.py
    # MUST NOT depend on it. We assert that re-importing self_corrections does
    # not require speakloop.llm.
    import importlib

    if "speakloop.llm" in sys.modules:
        del sys.modules["speakloop.llm"]
    if "speakloop.metrics.self_corrections" in sys.modules:
        del sys.modules["speakloop.metrics.self_corrections"]
    mod = importlib.import_module("speakloop.metrics.self_corrections")
    assert "speakloop.llm" not in sys.modules
    assert mod.self_corrections_count("the the") == 1
