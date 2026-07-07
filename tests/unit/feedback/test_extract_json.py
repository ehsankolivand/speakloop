"""Unit tests for grammar_analyzer JSON extraction + lenient repair.

Qwen sometimes emits JSON-like text with markdown fences, single quotes, or
trailing commas. `extract_json` must recover the common cases and, when it
genuinely can't, raise the original JSON error so `phase_c_error` shows it.
"""

from __future__ import annotations

import pytest

from speakloop.feedback import grammar_analyzer as ga  # for the SPEAKLOOP_DEBUG_LLM dump tests
from speakloop.feedback import json_recovery as jr

pytestmark = pytest.mark.unit


def test_clean_json():
    assert jr.extract_json('{"patterns": []}') == {"patterns": []}


def test_markdown_fenced_json():
    raw = '```json\n{"patterns": [{"label": "x", "occurrence_count": 2}]}\n```'
    assert jr.extract_json(raw) == {"patterns": [{"label": "x", "occurrence_count": 2}]}


def test_plain_fenced_json():
    raw = '```\n{"patterns": []}\n```'
    assert jr.extract_json(raw) == {"patterns": []}


def test_single_quoted_keys_and_values():
    raw = "{'patterns': [{'label': 'th-stopping', 'occurrence_count': 3}]}"
    assert jr.extract_json(raw) == {
        "patterns": [{"label": "th-stopping", "occurrence_count": 3}]
    }


def test_unquoted_keys():
    raw = '{patterns: [{label: "x", occurrence_count: 2}]}'
    assert jr.extract_json(raw) == {"patterns": [{"label": "x", "occurrence_count": 2}]}


def test_trailing_comma_json():
    raw = '{"patterns": [{"label": "x", "occurrence_count": 2,},],}'
    assert jr.extract_json(raw) == {"patterns": [{"label": "x", "occurrence_count": 2}]}


def test_junk_token_before_key_is_stripped():
    # Reasoning-model leak: a lone junk token before a quoted key (the live bug).
    raw = '{"patterns": [{"a": 1, b "c": 2}]}'
    assert jr.extract_json(raw) == {"patterns": [{"a": 1, "c": 2}]}


def test_junk_token_before_key_multiline():
    raw = (
        '{\n  "attempt_ordinal": 1,\n  a "quote": "use library",\n'
        '  "corrected": "use the library"\n}'
    )
    assert jr.extract_json(raw) == {
        "attempt_ordinal": 1,
        "quote": "use library",
        "corrected": "use the library",
    }


def test_extraneous_text_before_and_after():
    raw = 'Sure! Here is the analysis:\n{"patterns": []}\nLet me know if you need more.'
    assert jr.extract_json(raw) == {"patterns": []}


def test_fenced_with_preamble():
    raw = 'Here you go:\n```json\n{"patterns": [{"label": "y", "occurrence_count": 2}]}\n```'
    assert jr.extract_json(raw) == {"patterns": [{"label": "y", "occurrence_count": 2}]}


def test_no_json_object_raises_value_error():
    with pytest.raises(ValueError, match="Could not extract JSON"):
        jr.extract_json("I could not produce any JSON for this input.")


def test_missing_commas_now_recovered_by_json_repair():
    # 006: the json-repair ladder recovers what the old hand-rolled regex repair
    # raised on (missing commas). The non-dict items are dropped later in
    # _verify_and_enrich, so this is a strict improvement for SC-001/SC-004.
    assert jr.extract_json('{"patterns": [1 2 3]}') == {"patterns": [1, 2, 3]}


def test_truncated_object_recovered_by_json_repair():
    # The major SC-001 win: a cut-off object (hit max_tokens) used to raise because
    # the `\{.*\}` regex needs a closing brace; json-repair closes the structure.
    raw = '{"patterns": [{"label": "gerund", "occurrence_count": 2'
    assert jr.extract_json(raw) == {"patterns": [{"label": "gerund", "occurrence_count": 2}]}


def test_repair_does_not_corrupt_already_valid_json():
    # Strict parse path returns immediately; repairs never run on valid JSON.
    valid = '{"patterns": [{"label": "a, b", "occurrence_count": 2}]}'
    assert jr.extract_json(valid) == {"patterns": [{"label": "a, b", "occurrence_count": 2}]}


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
