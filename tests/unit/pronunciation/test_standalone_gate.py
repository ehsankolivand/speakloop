"""T018 (017) — the standalone RAM-only safety gate variant.

Asserts FR-011: `assess_standalone_safety` checks ONLY live memory (a configured local feedback
engine does not block it), while the 016 `assess_safety("local", …)` stays always-unsafe. No
model is ever loaded — these are pure decisions.
"""

from __future__ import annotations

import pytest

from speakloop.pronunciation import gate
from speakloop.pronunciation.gate import assess_safety, assess_standalone_safety

pytestmark = pytest.mark.unit


def test_high_ram_local_interview_unsafe_but_standalone_safe():
    # Same generous RAM: the interview gate still blocks `local` (engine penalty); standalone
    # ignores the engine and only sees RAM → safe.
    interview = assess_safety("local", min_free_mb=4500, available_mb=8000)
    standalone = assess_standalone_safety(min_free_mb=4500, available_mb=8000)
    assert interview.safe is False, "the 016 local-engine rule must stay unsafe"
    assert standalone.safe is True, "standalone has no resident engine → RAM-only → safe"
    assert standalone.engine == "standalone"


def test_low_ram_standalone_unsafe():
    d = assess_standalone_safety(min_free_mb=4500, available_mb=2000)
    assert d.safe is False
    assert "2000 MB free" in d.reason and "pronounce" in d.reason  # plain reason + remediation


def test_unreadable_ram_is_safe_cautious(monkeypatch):
    monkeypatch.setattr(gate, "_measure_available_mb", lambda: None)
    d = assess_standalone_safety(min_free_mb=4500)
    assert d.safe is True
    assert d.available_mb is None


def test_standalone_does_not_apply_engine_penalty():
    # A configured local engine is irrelevant to the standalone decision: only RAM matters.
    assert assess_standalone_safety(min_free_mb=4500, available_mb=6000).safe is True
    assert assess_standalone_safety(min_free_mb=4500, available_mb=100).safe is False
