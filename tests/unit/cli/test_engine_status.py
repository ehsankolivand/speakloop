"""T011 (015) — cli.engine_status readiness model (no live engine, no real binary)."""

from __future__ import annotations

import pytest

from speakloop.cli import engine_status
from speakloop.installer.validator import ValidationResult

pytestmark = pytest.mark.unit


def _fake_validate(monkeypatch, ok: bool):
    def _validate(model):
        return ValidationResult(
            ok=ok,
            reason="ok" if ok else "missing",
            measured_bytes=model.expected_size_bytes if ok else 0,
            expected_bytes=model.expected_size_bytes,
        )

    monkeypatch.setattr("speakloop.installer.validator.validate", _validate)


def test_local_ready_when_model_present(monkeypatch):
    _fake_validate(monkeypatch, ok=True)
    r = engine_status.engine_readiness("local")
    assert r.engine == "local"
    assert r.ready is True
    assert r.requirements[0].ok is True
    assert r.requirements[0].optional is False


def test_local_not_ready_when_model_absent(monkeypatch):
    _fake_validate(monkeypatch, ok=False)
    r = engine_status.engine_readiness("local")
    assert r.ready is False
    assert r.requirements[0].ok is False
    assert "setup" in r.requirements[0].next_step


def test_openrouter_requirement_is_optional(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("speakloop.llm.openrouter_credentials.resolve_token", lambda: None)
    r = engine_status.engine_readiness("openrouter")
    req = r.requirements[0]
    assert req.optional is True
    assert req.ok is False
    # Optional requirements never gate readiness.
    assert r.ready is True
    assert "OPENROUTER_API_KEY" in req.next_step


def test_openrouter_token_present(monkeypatch):
    monkeypatch.setattr("speakloop.llm.openrouter_credentials.resolve_token", lambda: "sk-or-x")
    r = engine_status.engine_readiness("openrouter")
    assert r.requirements[0].ok is True


def test_claude_requirements_use_probe_not_real_binary(monkeypatch):
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.doctor_probe",
        lambda: {"installed": True, "binary": "/usr/local/bin/claude", "logged_in": True},
    )
    r = engine_status.engine_readiness("claude")
    labels = {req.label for req in r.requirements}
    assert "Claude Code CLI" in labels
    assert "Claude Code auth" in labels
    assert all(req.optional for req in r.requirements)
    assert r.ready is True  # all optional → never blocks


def test_claude_not_installed(monkeypatch):
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.doctor_probe",
        lambda: {"installed": False, "binary": None, "logged_in": None},
    )
    r = engine_status.engine_readiness("claude")
    assert r.requirements[0].ok is False
    assert "install Claude Code" in r.requirements[0].next_step
