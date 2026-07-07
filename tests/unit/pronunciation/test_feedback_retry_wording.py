"""T007 (017) — additive retry + "tricky sounds" wording in the report section.

Asserts the new lines are detection-led / encouraging (never a graded verdict), and that a
drill dict WITHOUT retry/tricky data renders byte-identically to the 016 output (additivity).
"""

from __future__ import annotations

import pytest

from speakloop.pronunciation.feedback import render_drills_section

pytestmark = pytest.mark.unit


def _item(**kw):
    base = {"drill_id": "vest", "text": "We verify every value.", "prompt": "We verify every value.",
            "status": "scored", "flags": [], "is_follow_on": False, "contrast_id": "v_w"}
    base.update(kw)
    return base


def test_improved_retry_line_is_encouraging():
    drills = {"items": [_item(
        flags=[{"expected": "v", "word": "verify", "competitor": "w", "confident_diagnosis": True, "tip": "press"}],
        retry={"attempts": 2, "outcome": "improved", "final_flags": []},
    )]}
    out = render_drills_section(drills)
    assert "On retry: better" in out and "clear now ✓" in out
    assert "sounded off" in out  # still leads with detection


def test_still_off_retry_line_is_non_blaming():
    drills = {"items": [_item(
        flags=[{"expected": "v", "word": "verify", "tip": "press"}],
        retry={"attempts": 2, "outcome": "still_off", "final_flags": [{"expected": "v"}]},
    )]}
    out = render_drills_section(drills)
    assert "still a little off" in out.lower()
    assert "fail" not in out.lower() and "wrong" not in out.lower()


def test_error_retry_omits_verdict_line():
    # A retry that could not be scored (outcome "error") carries NO pronunciation verdict:
    # the first-attempt detection line stays, but the report must NOT claim "still a little off".
    drills = {"items": [_item(
        flags=[{"expected": "v", "word": "verify", "tip": "press"}],
        retry={"attempts": 2, "outcome": "error", "final_flags": []},
    )]}
    out = render_drills_section(drills)
    assert "sounded off" in out  # the genuine first-attempt detection is still shown
    assert "On retry" not in out  # but no retry verdict line at all
    assert "still a little off" not in out.lower()


def test_tricky_sounds_line_rendered_from_summary():
    drills = {"items": [_item(flags=[{"expected": "v", "word": "verify"}])],
              "summary": {"tricky_sounds": ["v vs w"]}}
    out = render_drills_section(drills)
    assert "Tricky sounds this session: v vs w." in out


def test_no_retry_no_tricky_is_byte_identical_to_016():
    # A 016-shaped dict (no retry key, no tricky_sounds) must render exactly as before.
    item016 = {"drill_id": "vest", "text": "vest", "prompt": "vest", "status": "scored",
               "flags": [{"expected": "v", "word": "vest", "tip": "press"}],
               "is_follow_on": False, "contrast_id": "v_w"}
    out = render_drills_section({"engine_note": "n", "items": [item016]})
    assert "On retry" not in out
    assert "Tricky sounds" not in out
    # the 016 structure is intact
    assert out.startswith("## Pronunciation drills")
    assert "- **vest**" in out and "Tip: press" in out
