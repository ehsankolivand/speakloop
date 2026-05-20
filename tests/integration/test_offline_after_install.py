"""T106 — SC-009 / FR-023 / FR-037: speakloop is offline-only after install.

Strategy: monkeypatch `socket.socket` so any attempted network connection
during `practice` or `trends` raises immediately. The installer's
`huggingface_hub.snapshot_download` is the only intentional network site,
and `practice --listen-only` reaches a working session before the installer
runs by validating already-present models, so the test pre-validates
models and then verifies no socket is opened during the run.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app
from speakloop.installer.validator import ValidationResult

pytestmark = pytest.mark.integration


class NetworkAccessError(AssertionError):
    """Raised the moment any socket attempts to open."""


@pytest.fixture
def block_network(monkeypatch):
    """Replace socket.socket so any network attempt fails loudly."""
    opened: list[tuple] = []
    real_socket = socket.socket

    class _BlockedSocket(real_socket):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            opened.append(("__init__", args, kwargs))
            super().__init__(*args, **kwargs)

        def connect(self, address):
            raise NetworkAccessError(
                f"Network access attempted while offline: connect({address!r})"
            )

        def connect_ex(self, address):
            raise NetworkAccessError(
                f"Network access attempted while offline: connect_ex({address!r})"
            )

    monkeypatch.setattr(socket, "socket", _BlockedSocket)
    yield opened


def _pretend_models_present(monkeypatch):
    def fake_validate(model):
        return ValidationResult(
            ok=True,
            reason="ok",
            measured_bytes=model.expected_size_bytes,
            expected_bytes=model.expected_size_bytes,
        )

    from speakloop import installer as _installer

    monkeypatch.setattr(_installer.validator, "validate", fake_validate)


def test_practice_listen_only_makes_no_network_connection(
    block_network, monkeypatch, tmp_path, wav_fixture, starter_question_id, default_questions_text
):
    qa_file = tmp_path / "qa.yaml"
    # 004: no first-run auto-copy; pre-populate the explicit override file.
    qa_file.write_text(default_questions_text, encoding="utf-8")
    monkeypatch.setenv("SPEAKLOOP_QA_FILE", str(qa_file))
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SPEAKLOOP_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(tmp_path / "models"))

    _pretend_models_present(monkeypatch)

    q_wav = wav_fixture("question-short.wav")
    a_wav = wav_fixture("ideal-answer-short.wav")

    class StubTTS:
        def synthesize(self, text, voice=None):
            return q_wav if "Kotlin" in text else a_wav

        def available_voices(self):
            return []

    monkeypatch.setattr(
        "speakloop.tts.kokoro_engine.KokoroEngine", lambda *a, **k: StubTTS()
    )
    monkeypatch.setattr("speakloop.audio.playback.play", lambda p: None)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["practice", "--listen-only", "--question", starter_question_id],
        input="\n",
    )
    assert result.exit_code == 0, result.stdout
    # The CLI MUST NOT have constructed any socket during practice.
    assert block_network == [], f"Unexpected socket activity: {block_network}"


def test_trends_makes_no_network_connection(block_network, tmp_path):
    fixtures_dir = Path(__file__).parents[1] / "fixtures" / "sessions"
    runner = CliRunner()
    result = runner.invoke(app, ["trends", "--sessions-dir", str(fixtures_dir)])
    assert result.exit_code == 0, result.stdout
    assert block_network == [], f"Unexpected socket activity: {block_network}"


def test_doctor_makes_no_network_connection(block_network, monkeypatch, tmp_sessions_dir):
    _pretend_models_present(monkeypatch)
    from speakloop.audio import devices

    class _Info:
        name = "Built-in"
        default_samplerate = 48000

    monkeypatch.setattr(devices, "default_input", lambda: _Info())
    monkeypatch.setattr(devices, "default_output", lambda: _Info())

    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.stdout
    assert block_network == [], f"Unexpected socket activity: {block_network}"
