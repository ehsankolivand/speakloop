"""T089 — doctor command behaviour."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app

pytestmark = pytest.mark.unit

runner = CliRunner()


def _fake_devices(monkeypatch, *, input_ok: bool = True, output_ok: bool = True):
    from speakloop.audio import devices

    class _Info:
        name = "Built-in"
        default_samplerate = 48000

    monkeypatch.setattr(devices, "default_input", lambda: _Info() if input_ok else None)
    monkeypatch.setattr(devices, "default_output", lambda: _Info() if output_ok else None)


def _fake_validator(monkeypatch, *, all_ok: bool = True):
    """Replace validator.validate so we don't have to write multi-GB files."""
    from speakloop.cli import doctor as _doctor
    from speakloop.installer.validator import ValidationResult

    def _validate(model):
        if all_ok:
            return ValidationResult(
                ok=True,
                reason="ok",
                measured_bytes=model.expected_size_bytes,
                expected_bytes=model.expected_size_bytes,
            )
        return ValidationResult(
            ok=False, reason="missing", expected_bytes=model.expected_size_bytes
        )

    monkeypatch.setattr(_doctor.validator, "validate", _validate)


def test_doctor_passes_when_everything_ok(monkeypatch, tmp_sessions_dir):
    _fake_validator(monkeypatch, all_ok=True)
    _fake_devices(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_missing_model_fails(monkeypatch, tmp_sessions_dir):
    _fake_validator(monkeypatch, all_ok=False)
    _fake_devices(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0
    assert "FAIL" in result.stdout
    assert "speakloop practice" in result.stdout


def test_no_output_device_fails(monkeypatch, tmp_sessions_dir):
    _fake_validator(monkeypatch, all_ok=True)
    _fake_devices(monkeypatch, output_ok=False)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0
    assert "FAIL" in result.stdout


def test_json_emits_parseable_json(monkeypatch, tmp_sessions_dir):
    _fake_validator(monkeypatch, all_ok=True)
    _fake_devices(monkeypatch)
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert all("status" in row for row in parsed)


# --- 015: engine-aware readiness ------------------------------------------


def _no_claude_binary(monkeypatch):
    """Never touch the real claude binary from the doctor probe."""
    monkeypatch.setattr(
        "speakloop.llm.claude_code_engine.doctor_probe",
        lambda: {"installed": False, "binary": None, "version": None, "logged_in": None,
                 "api_key_in_env": False},
    )


def _validate_no_local_llm(monkeypatch):
    """TTS/ASR present, the local feedback LLM (phase C) absent."""
    from speakloop.cli import doctor as _doctor
    from speakloop.installer.validator import ValidationResult

    def _validate(model):
        ok = model.required_for_phase != "C"
        return ValidationResult(
            ok=ok,
            reason="ok" if ok else "missing",
            measured_bytes=model.expected_size_bytes if ok else 0,
            expected_bytes=model.expected_size_bytes,
        )

    monkeypatch.setattr(_doctor.validator, "validate", _validate)


def test_doctor_reports_active_engine(monkeypatch, tmp_sessions_dir):
    _fake_validator(monkeypatch, all_ok=True)
    _fake_devices(monkeypatch)
    _no_claude_binary(monkeypatch)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "active engine" in result.stdout
    assert "local" in result.stdout


def test_cloud_engine_missing_local_llm_does_not_fail(monkeypatch, tmp_path, tmp_sessions_dir):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from speakloop.config import loop_config

    loop_config.save_engine("openrouter")
    _validate_no_local_llm(monkeypatch)
    _fake_devices(monkeypatch)
    _no_claude_binary(monkeypatch)

    result = runner.invoke(app, ["doctor"])
    # A cloud user missing only the local LLM is healthy.
    assert result.exit_code == 0
    assert "openrouter" in result.stdout
    assert "not required for the active engine" in result.stdout


def test_local_engine_missing_llm_still_fails(monkeypatch, tmp_path, tmp_sessions_dir):
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "home"))
    from speakloop.config import loop_config

    loop_config.save_engine("local")
    _validate_no_local_llm(monkeypatch)
    _fake_devices(monkeypatch)
    _no_claude_binary(monkeypatch)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0  # local engine genuinely not ready
    assert "FAIL" in result.stdout


def test_doctor_probes_claude_once_when_engine_claude(monkeypatch, tmp_path, tmp_sessions_dir):
    """The credit-free claude probe must run once per `doctor`, not once per section."""
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "home"))
    from speakloop.config import loop_config

    loop_config.save_engine("claude")
    _fake_validator(monkeypatch, all_ok=True)
    _fake_devices(monkeypatch)
    calls = {"n": 0}

    def _probe():
        calls["n"] += 1
        return {"installed": True, "binary": "/x/claude", "version": "2.1",
                "logged_in": True, "auth_method": "subscription", "subscription_type": "max",
                "api_key_in_env": False}

    monkeypatch.setattr("speakloop.llm.claude_code_engine.doctor_probe", _probe)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert calls["n"] == 1
