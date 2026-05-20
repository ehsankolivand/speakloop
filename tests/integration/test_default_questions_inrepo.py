"""T012 (004) — with no --qa-file and no ~/.speakloop/qa.yaml override, the practice
flow resolves and loads the in-repo default content/questions.yaml (US1 acceptance 1-2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app
from speakloop.config import paths
from speakloop.content import load
from speakloop.installer.validator import ValidationResult

pytestmark = pytest.mark.integration


def test_resolve_falls_back_to_inrepo_default(monkeypatch, tmp_path):
    # Point the speakloop home at an empty tmp dir so the personal override
    # (~/.speakloop/qa.yaml) is guaranteed absent, and clear any explicit override.
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    monkeypatch.delenv("SPEAKLOOP_QA_FILE", raising=False)
    paths.set_qa_file_path(None)

    resolved = paths.resolve_qa_file()
    assert resolved == paths.default_qa_file()
    assert resolved.name == "questions.yaml"
    assert resolved.exists(), "in-repo default content/questions.yaml must exist"

    qa = load(resolved)
    assert len(qa.questions) >= 1


def test_practice_listen_only_uses_inrepo_default(
    monkeypatch, tmp_path, wav_fixture, starter_question_id
):
    # No SPEAKLOOP_QA_FILE and an empty SPEAKLOOP_HOME → resolution must reach the
    # in-repo default content/questions.yaml on its own.
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path))
    monkeypatch.delenv("SPEAKLOOP_QA_FILE", raising=False)
    paths.set_qa_file_path(None)
    sessions_dir = tmp_path / "data" / "sessions"
    sessions_dir.mkdir(parents=True)
    monkeypatch.setenv("SPEAKLOOP_TTS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SPEAKLOOP_SESSIONS_DIR", str(sessions_dir))
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(tmp_path / "models"))

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
        def synthesize(self, text, voice=None):
            return q_wav if "rotat" in text.lower() else a_wav

        def available_voices(self):
            return ["bm_george"]

    monkeypatch.setattr("speakloop.tts.kokoro_engine.KokoroEngine", lambda *a, **k: StubTTS())
    monkeypatch.setattr("speakloop.audio.playback.play", lambda p: None)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["practice", "--listen-only", "--question", starter_question_id],
        input="\n",
    )
    assert result.exit_code == 0, result.stdout
    # The default lives in the repo, not the (empty) home dir — nothing was created there.
    assert not (Path(tmp_path) / "qa.yaml").exists()
