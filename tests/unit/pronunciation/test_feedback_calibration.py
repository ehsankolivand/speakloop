"""T013 — pronunciation feedback is detection-led and hedges diagnosis (FR-009)."""

from __future__ import annotations

import pytest

from speakloop.pronunciation import feedback

pytestmark = pytest.mark.unit


def _drill(items):
    return {"engine_note": "", "items": items}


def test_no_items_renders_none():
    assert feedback.render_drills_section(None) is None
    assert feedback.render_drills_section(_drill([])) is None


def test_detection_stated_diagnosis_hidden_when_not_confident():
    section = feedback.render_drills_section(
        _drill(
            [
                {
                    "text": "west",
                    "status": "scored",
                    "flags": [
                        {
                            "expected": "w",
                            "word": "west",
                            "competitor": "ɹ",
                            "confident_diagnosis": False,
                            "tip": "Round your lips.",
                        }
                    ],
                }
            ]
        )
    )
    assert section is not None
    assert "sounded off" in section  # detection stated
    # the SPECIFIC diagnosis is withheld when not confident (the word "suggestion" still
    # appears in the always-present calibration disclaimer — check the diagnosis text itself):
    assert "may have come out closer to" not in section
    assert "ɹ" not in section  # the competitor symbol is not surfaced
    assert "Round your lips." in section


def test_confident_diagnosis_is_hedged_never_a_verdict():
    section = feedback.render_drills_section(
        _drill(
            [
                {
                    "text": "west",
                    "status": "scored",
                    "flags": [
                        {
                            "expected": "w",
                            "word": "west",
                            "competitor": "ɹ",
                            "confident_diagnosis": True,
                            "tip": "Round your lips.",
                        }
                    ],
                }
            ]
        )
    )
    assert "sounded off" in section
    assert "suggestion" in section  # hedged
    assert "may have come out closer to" in section  # not a verdict


def test_not_captured_and_error_are_honest_not_failures():
    section = feedback.render_drills_section(
        _drill(
            [
                {"text": "thin", "status": "not_captured", "flags": []},
                {"text": "vest", "status": "error", "flags": []},
                {"text": "this", "status": "scored", "flags": []},
            ]
        )
    )
    assert "not captured" in section
    assert "could not score" in section
    assert "clear ✓" in section  # a clean read is acknowledged
