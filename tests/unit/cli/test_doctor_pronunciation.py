"""T033 (016) — the doctor Pronunciation-drills section renders and never FAILs the exit code.

A user who never opts into drills (model absent) must still get `doctor` exit 0.
"""

from __future__ import annotations

import pytest

from speakloop.cli import doctor

pytestmark = pytest.mark.unit


def test_pronunciation_section_rows_render_and_never_fail():
    rows = doctor._pronunciation()
    sections = {r.section for r in rows}
    assert sections == {"Pronunciation drills"}
    labels = {r.label for r in rows}
    assert {"model", "setting", "availability"} <= labels
    # opt-in feature: NONE of its rows may be FAIL (model absent ⇒ WARN, not FAIL).
    assert all(r.status != "FAIL" for r in rows)


def test_full_doctor_collect_never_fails_from_pronunciation(monkeypatch):
    # Force the local claude probe so no real subprocess runs.
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.doctor_probe",
        lambda: {"installed": False, "binary": None, "version": None, "logged_in": False},
    )
    rows = doctor._collect()
    pron = [r for r in rows if r.section == "Pronunciation drills"]
    assert pron, "doctor must include the Pronunciation drills section"
    assert all(r.status != "FAIL" for r in pron)
