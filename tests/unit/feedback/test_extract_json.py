"""Unit tests for grammar_analyzer JSON extraction + lenient repair.

Qwen sometimes emits JSON-like text with markdown fences, single quotes, or
trailing commas. `_extract_json` must recover the common cases and, when it
genuinely can't, raise the original JSON error so `phase_c_error` shows it.
"""

from __future__ import annotations

import json

import pytest

from speakloop.feedback import grammar_analyzer as ga

pytestmark = pytest.mark.unit


def test_clean_json():
    assert ga._extract_json('{"patterns": []}') == {"patterns": []}


def test_markdown_fenced_json():
    raw = '```json\n{"patterns": [{"label": "x", "occurrence_count": 2}]}\n```'
    assert ga._extract_json(raw) == {"patterns": [{"label": "x", "occurrence_count": 2}]}


def test_plain_fenced_json():
    raw = '```\n{"patterns": []}\n```'
    assert ga._extract_json(raw) == {"patterns": []}


def test_single_quoted_keys_and_values():
    raw = "{'patterns': [{'label': 'th-stopping', 'occurrence_count': 3}]}"
    assert ga._extract_json(raw) == {
        "patterns": [{"label": "th-stopping", "occurrence_count": 3}]
    }


def test_unquoted_keys():
    raw = '{patterns: [{label: "x", occurrence_count: 2}]}'
    assert ga._extract_json(raw) == {"patterns": [{"label": "x", "occurrence_count": 2}]}


def test_trailing_comma_json():
    raw = '{"patterns": [{"label": "x", "occurrence_count": 2,},],}'
    assert ga._extract_json(raw) == {"patterns": [{"label": "x", "occurrence_count": 2}]}


def test_junk_token_before_key_is_stripped():
    # Reasoning-model leak: a lone junk token before a quoted key (the live bug).
    raw = '{"patterns": [{"a": 1, b "c": 2}]}'
    assert ga._extract_json(raw) == {"patterns": [{"a": 1, "c": 2}]}


def test_junk_token_before_key_multiline():
    raw = (
        '{\n  "attempt_ordinal": 1,\n  a "quote": "use library",\n'
        '  "corrected": "use the library"\n}'
    )
    assert ga._extract_json(raw) == {
        "attempt_ordinal": 1,
        "quote": "use library",
        "corrected": "use the library",
    }


def test_extraneous_text_before_and_after():
    raw = 'Sure! Here is the analysis:\n{"patterns": []}\nLet me know if you need more.'
    assert ga._extract_json(raw) == {"patterns": []}


def test_fenced_with_preamble():
    raw = 'Here you go:\n```json\n{"patterns": [{"label": "y", "occurrence_count": 2}]}\n```'
    assert ga._extract_json(raw) == {"patterns": [{"label": "y", "occurrence_count": 2}]}


def test_no_json_object_raises_value_error():
    with pytest.raises(ValueError, match="Could not extract JSON"):
        ga._extract_json("I could not produce any JSON for this input.")


def test_unrepairable_json_raises_original_decode_error():
    # Has braces (so extraction proceeds) but is not repairable (missing commas).
    with pytest.raises(json.JSONDecodeError):
        ga._extract_json('{"patterns": [1 2 3]}')


def test_repair_does_not_corrupt_already_valid_json():
    # Strict parse path returns immediately; repairs never run on valid JSON.
    valid = '{"patterns": [{"label": "a, b", "occurrence_count": 2}]}'
    assert ga._extract_json(valid) == {"patterns": [{"label": "a, b", "occurrence_count": 2}]}


# --- diagnostic dump gating (SPEAKLOOP_DEBUG_LLM) -----------------------------


def test_debug_dump_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SPEAKLOOP_DEBUG_LLM", raising=False)
    assert ga._debug_dump_raw("some raw output") is None


def test_debug_dump_writes_when_enabled(monkeypatch, tmp_sessions_dir):
    monkeypatch.setenv("SPEAKLOOP_DEBUG_LLM", "1")
    path = ga._debug_dump_raw("RAW-QWEN-OUTPUT-12345")
    assert path is not None
    from pathlib import Path

    p = Path(path)
    assert p.exists()
    assert p.parent.name == ".debug-llm-raw"
    assert "RAW-QWEN-OUTPUT-12345" in p.read_text()
