"""T042 — Phase A listen flow end-to-end via CliRunner with stub TTS + mocked playback."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app
from speakloop.installer.validator import ValidationResult

pytestmark = pytest.mark.integration


def test_listen_only_flow(monkeypatch, tmp_path, wav_fixture):
    qa_file = tmp_path / "qa.yaml"
    cache_dir = tmp_path / "cache"
    sessions_dir = tmp_path / "data" / "sessions"
    sessions_dir.mkdir(parents=True)
    monkeypatch.setenv("SPEAKLOOP_QA_FILE", str(qa_file))
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("SPEAKLOOP_SESSIONS_DIR", str(sessions_dir))
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(tmp_path / "models"))

    # Pretend models are validated (avoid writing 327 MB of fake weights).
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
    a_wav = wav_fixture("ideal-answer-short.wav")

    class StubTTS:
        def __init__(self) -> None:
            self.calls = []

        def synthesize(self, text, voice=None):
            self.calls.append((text.strip()[:30], voice))
            return q_wav if "Explain how Kotlin" in text else a_wav

        def available_voices(self):
            return ["bm_george"]

    play_calls = []

    def mock_play(p):
        play_calls.append(Path(p))

    monkeypatch.setattr("speakloop.tts.kokoro_engine.KokoroEngine", lambda *a, **k: StubTTS())
    monkeypatch.setattr("speakloop.audio.playback.play", mock_play)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["practice", "--listen-only", "--question", "kotlin-coroutines-basics"],
        input="\n",
    )

    assert result.exit_code == 0, result.stdout
    assert len(play_calls) >= 2
    assert list(sessions_dir.iterdir()) == []
    assert qa_file.exists()
