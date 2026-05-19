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
