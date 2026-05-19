"""T063 — practice refuses to start attempts when no mic; remediates to doctor."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app
from speakloop.installer.validator import ValidationResult

pytestmark = pytest.mark.integration


def test_no_microphone_exits_one(monkeypatch, tmp_path, wav_fixture):
    qa_file = tmp_path / "qa.yaml"
    monkeypatch.setenv("SPEAKLOOP_QA_FILE", str(qa_file))
    monkeypatch.setenv("SPEAKLOOP_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(tmp_path / "cache"))

    # Pretend all models are validated (no disk write).
    def fake_validate(model):
        return ValidationResult(
            ok=True,
            reason="ok",
            measured_bytes=model.expected_size_bytes,
            expected_bytes=model.expected_size_bytes,
        )

    from speakloop import installer as _installer

    monkeypatch.setattr(_installer.validator, "validate", fake_validate)

    q_wav = wav_fixture("question-short.wav")

    class StubTTS:
        def synthesize(self, text, voice=None):
            return q_wav

        def available_voices(self):
            return []

    monkeypatch.setattr("speakloop.tts.kokoro_engine.KokoroEngine", lambda *a, **k: StubTTS())
    monkeypatch.setattr("speakloop.audio.playback.play", lambda p: None)
    monkeypatch.setattr("speakloop.audio.devices.default_input", lambda: None)

    runner = CliRunner()
    # "space\n" → listen loop advances to the attempt phase, where the mic
    # check should fail. Empty input would now mean "quit" (the listen loop
    # treats Enter / EOF as exit-cleanly).
    result = runner.invoke(
        app,
        ["practice", "--question", "kotlin-coroutines-basics"],
        input="space\n",
    )
    assert result.exit_code == 1
    assert "microphone" in result.stdout.lower() or "doctor" in result.stdout.lower()
