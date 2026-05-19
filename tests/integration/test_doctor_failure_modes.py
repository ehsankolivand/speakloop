"""T090 — exhaustive sweep of failure modes."""

from __future__ import annotations

import os
import stat

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app
from speakloop.installer import manifest

pytestmark = pytest.mark.integration

runner = CliRunner()


def _fake_devices(monkeypatch, *, input_ok=True, output_ok=True):
    from speakloop.audio import devices

    class _Info:
        name = "Built-in"
        default_samplerate = 48000

    monkeypatch.setattr(devices, "default_input", lambda: _Info() if input_ok else None)
    monkeypatch.setattr(devices, "default_output", lambda: _Info() if output_ok else None)


def test_failures_are_all_reported_in_one_run(monkeypatch, tmp_models_dir, tmp_sessions_dir):
    """SC-007: every breakable precondition reported in a single run."""
    # No models, no input device, output OK, sessions read-only.
    _fake_devices(monkeypatch, input_ok=False, output_ok=False)
    # Make sessions_dir read-only.
    os.chmod(tmp_sessions_dir, stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = runner.invoke(app, ["doctor"])
        out = result.stdout
        assert "FAIL" in out
        # All three model rows present even on failure.
        for m in manifest.PHASE_C_MODELS:
            assert m.name in out
        assert "sessions_dir" in out
        assert "audio" in out.lower() or "Audio" in out
    finally:
        # restore permissions so pytest cleanup works
        os.chmod(tmp_sessions_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
