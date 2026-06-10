"""Integration: `speakloop doctor` Claude Code rows (011) — monkeypatched probe, no real CLI."""

from __future__ import annotations

import pytest

from speakloop.cli import doctor

pytestmark = pytest.mark.integration


def _patch_probe(monkeypatch, info):
    monkeypatch.setattr("speakloop.llm.claude_code_engine.doctor_probe", lambda: info)


_LOGGED_IN = {
    "installed": True,
    "binary": "/opt/homebrew/bin/claude",
    "version": "2.1.170",
    "logged_in": True,
    "auth_method": "claude.ai",
    "subscription_type": "max",
    "api_key_in_env": False,
    "error": None,
}
_NOT_INSTALLED = {
    "installed": False,
    "binary": None,
    "version": None,
    "logged_in": None,
    "auth_method": None,
    "subscription_type": None,
    "api_key_in_env": False,
    "error": None,
}


def test_rows_when_logged_in(monkeypatch):
    _patch_probe(monkeypatch, _LOGGED_IN)
    rows = doctor._claude_code()
    by_label = {r.label: r for r in rows}
    assert by_label["CLI binary"].status == "OK"
    assert by_label["version"].detail == "2.1.170"
    assert "logged in" in by_label["authentication"].detail
    assert "claude.ai" in by_label["authentication"].detail
    assert any(r.label == "default engine" for r in rows)
    assert all(r.status != "FAIL" for r in rows)  # opt-in: never FAIL


def test_rows_when_not_installed(monkeypatch):
    _patch_probe(monkeypatch, _NOT_INSTALLED)
    rows = doctor._claude_code()
    binrow = next(r for r in rows if r.label == "CLI binary")
    assert binrow.status == "WARN"
    assert "not found" in binrow.detail
    assert all(r.status != "FAIL" for r in rows)


def test_rows_when_logged_out(monkeypatch):
    info = {**_LOGGED_IN, "logged_in": False, "auth_method": None, "subscription_type": None}
    _patch_probe(monkeypatch, info)
    rows = doctor._claude_code()
    auth = next(r for r in rows if r.label == "authentication")
    assert auth.status == "WARN"
    assert "logged out" in auth.detail
    assert "/login" in auth.remediation


def test_warns_when_api_key_in_env(monkeypatch):
    _patch_probe(monkeypatch, {**_LOGGED_IN, "api_key_in_env": True})
    rows = doctor._claude_code()
    keyrow = next(r for r in rows if r.label == "ANTHROPIC_API_KEY")
    assert keyrow.status == "WARN"
    assert "subscription" in keyrow.remediation


def test_collect_never_fails_due_to_claude_section(monkeypatch):
    _patch_probe(monkeypatch, _NOT_INSTALLED)
    claude_rows = [r for r in doctor._collect() if r.section == "Claude Code"]
    assert claude_rows
    assert all(r.status != "FAIL" for r in claude_rows)
