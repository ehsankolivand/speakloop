"""T018 (016) — CLI wiring of the pronunciation safety gate.

Asserts the gate is authoritative: a local engine (or the `off` setting) never builds a
scorer; `on` + safe builds it; the dangerous unsafe override is reachable ONLY via an
explicit interactive "yes" to the freeze warning. No real model/mic/prompt.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop import pronunciation
from speakloop.cli import practice
from speakloop.installer import manifest
from speakloop.pronunciation.gate import SafetyDecision

pytestmark = pytest.mark.unit


@pytest.fixture
def _no_real_build(monkeypatch):
    """Capture scorer construction + model download so no heavy work runs."""
    calls = {"ensure": 0, "build": 0, "gate": 0}

    monkeypatch.setattr(
        "speakloop.installer.ensure_pronunciation_model",
        lambda **kw: calls.__setitem__("ensure", calls["ensure"] + 1),
    )
    monkeypatch.setattr(
        pronunciation, "build_scorer", lambda: calls.__setitem__("build", calls["build"] + 1) or object()
    )
    monkeypatch.setattr(
        pronunciation, "load_drill_bank", lambda *a, **k: object()
    )
    return calls


def _console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False, width=120)


def _patch_gate(monkeypatch, *, safe: bool):
    def _fake(engine, *, min_free_mb, available_mb=None):
        return SafetyDecision(safe=safe, reason="because reasons", available_mb=None, engine=engine)

    monkeypatch.setattr(pronunciation, "assess_safety", _fake)


def test_setting_off_never_calls_the_gate_or_builds(monkeypatch, _no_real_build):
    gate_called = {"n": 0}
    monkeypatch.setattr(
        pronunciation,
        "assess_safety",
        lambda *a, **k: gate_called.__setitem__("n", 1) or SafetyDecision(True, "", None, "x"),
    )
    out = practice._resolve_pronunciation_drills(
        "openrouter", _console(), drills_flag=False, input_fn=lambda *_: "y"
    )
    assert out is None
    assert gate_called["n"] == 0  # `off` short-circuits BEFORE the gate
    assert _no_real_build["build"] == 0


def test_local_engine_unsafe_default_skips_and_never_builds(monkeypatch, _no_real_build):
    # Real gate: local is always unsafe. Non-interactive ⇒ no override prompt ⇒ skip.
    monkeypatch.setattr(practice, "_is_interactive", lambda: False)
    out = practice._resolve_pronunciation_drills(
        "local", _console(), drills_flag=None, input_fn=lambda *_: "yes"
    )
    assert out is None
    assert _no_real_build["build"] == 0
    assert _no_real_build["ensure"] == 0


def test_safe_on_builds_without_prompt(monkeypatch, _no_real_build):
    _patch_gate(monkeypatch, safe=True)
    monkeypatch.setattr(practice, "_is_interactive", lambda: False)
    out = practice._resolve_pronunciation_drills(
        "openrouter", _console(), drills_flag=True, input_fn=lambda *_: (_ for _ in ()).throw(AssertionError("prompted!"))
    )
    assert out is not None
    assert _no_real_build["build"] == 1
    assert _no_real_build["ensure"] == 1


def test_safe_auto_noninteractive_skips(monkeypatch, _no_real_build):
    _patch_gate(monkeypatch, safe=True)
    monkeypatch.setattr(practice, "_is_interactive", lambda: False)
    # default setting is auto (no flag); non-interactive auto can't consent ⇒ skip
    out = practice._resolve_pronunciation_drills(
        "openrouter", _console(), drills_flag=None, input_fn=lambda *_: "y"
    )
    assert out is None
    assert _no_real_build["build"] == 0


def test_safe_auto_interactive_yes_builds(monkeypatch, _no_real_build):
    _patch_gate(monkeypatch, safe=True)
    monkeypatch.setattr(practice, "_is_interactive", lambda: True)
    out = practice._resolve_pronunciation_drills(
        "openrouter", _console(), drills_flag=None, input_fn=lambda *_: "y"
    )
    assert out is not None
    assert _no_real_build["build"] == 1


def test_safe_auto_interactive_no_skips(monkeypatch, _no_real_build):
    _patch_gate(monkeypatch, safe=True)
    monkeypatch.setattr(practice, "_is_interactive", lambda: True)
    out = practice._resolve_pronunciation_drills(
        "openrouter", _console(), drills_flag=None, input_fn=lambda *_: "n"
    )
    assert out is None
    assert _no_real_build["build"] == 0


def test_unsafe_override_requires_explicit_yes(monkeypatch, _no_real_build):
    _patch_gate(monkeypatch, safe=False)
    monkeypatch.setattr(practice, "_is_interactive", lambda: True)
    # explicit "yes" to the freeze warning ⇒ proceed
    out = practice._resolve_pronunciation_drills(
        "openrouter", _console(), drills_flag=True, input_fn=lambda *_: "yes"
    )
    assert out is not None
    assert _no_real_build["build"] == 1


def test_unsafe_override_declined_skips(monkeypatch, _no_real_build):
    _patch_gate(monkeypatch, safe=False)
    monkeypatch.setattr(practice, "_is_interactive", lambda: True)
    out = practice._resolve_pronunciation_drills(
        "openrouter", _console(), drills_flag=True, input_fn=lambda *_: ""  # not "yes"
    )
    assert out is None
    assert _no_real_build["build"] == 0


def test_bundle_carries_the_model_repo_via_manifest():
    # sanity: the model the bundle would download is the verified Apache-2.0 wav2vec2 model.
    assert manifest.WAV2VEC2_PRONUNCIATION.hf_repo_id == "facebook/wav2vec2-lv-60-espeak-cv-ft"
