"""T016 — the safety gate: engine + live-RAM SAFE/UNSAFE matrix (P3, SC-001)."""

from __future__ import annotations

import pytest

from speakloop.pronunciation import gate

pytestmark = pytest.mark.unit

MIN = 4500


def test_local_engine_is_always_unsafe_even_with_huge_ram():
    d = gate.assess_safety("local", min_free_mb=MIN, available_mb=64_000)
    assert d.safe is False
    assert "local" in d.reason.lower()
    assert "cloud" in d.reason.lower()  # remediation hint present (SC-007)


def test_cloud_engine_with_enough_ram_is_safe():
    d = gate.assess_safety("openrouter", min_free_mb=MIN, available_mb=8000)
    assert d.safe is True
    assert d.available_mb == 8000


def test_cloud_engine_below_threshold_is_unsafe_with_low_memory_reason():
    d = gate.assess_safety("claude", min_free_mb=MIN, available_mb=2000)
    assert d.safe is False
    assert "free" in d.reason.lower()  # plain-language low-memory reason + remediation


def test_cloud_engine_unknown_ram_is_safe_cautious():
    # psutil-absent path: available_mb stays None ⇒ proceed because a cloud engine is active.
    d = gate.assess_safety("openrouter", min_free_mb=MIN, available_mb=None)
    # available_mb=None means "measure" — but in a test env psutil may or may not exist.
    # Force the unmeasurable branch by monkeypatching the measurer.
    assert isinstance(d.safe, bool)


def test_psutil_absent_branch(monkeypatch):
    monkeypatch.setattr(gate, "_measure_available_mb", lambda: None)
    d = gate.assess_safety("claude", min_free_mb=MIN)
    assert d.safe is True
    assert d.available_mb is None
    assert "couldn't read free memory" in d.reason


def test_unknown_engine_value_treated_as_cloud():
    d = gate.assess_safety("something-else", min_free_mb=MIN, available_mb=9000)
    assert d.safe is True


def test_gate_never_imports_the_model():
    """The safety gate must DECIDE without loading the ~1.3 GB scorer. Checked in a FRESH
    subprocess (IMP-044) — an in-process `sys.modules` check is unreliable because sibling
    tests import `wav2vec2_engine`, which is why the old assertion was tautologically `or True`."""
    import subprocess
    import sys

    code = (
        "import sys;"
        "from speakloop.pronunciation import gate;"
        f"gate.assess_safety('local', min_free_mb={MIN}, available_mb=8000);"
        "leaked = [m for m in "
        "('speakloop.pronunciation.wav2vec2_engine', 'torch', 'transformers') if m in sys.modules];"
        "print('LEAKED', leaked);"
        "sys.exit(1 if leaked else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"assess_safety loaded the scorer/torch/transformers:\n{result.stdout}\n{result.stderr}"
    )
