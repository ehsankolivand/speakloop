"""T015 (015) — practice provisions by engine; declining the local LLM degrades."""

from __future__ import annotations

import pytest
import typer

from speakloop import installer
from speakloop.cli import practice

pytestmark = pytest.mark.integration

_QA = (
    "schema_version: 1\n"
    "questions:\n"
    "  - id: q1\n"
    "    question: |\n"
    "      What is X?\n"
    "    ideal_answer: |\n"
    "      X is Y.\n"
)


class _StubTTS:
    def synthesize(self, text, voice=None):  # never reached — mic check fails first
        raise AssertionError("synthesize should not run; mic check stops the run")

    def available_voices(self):
        return []


class _NoMicDevices:
    @staticmethod
    def default_input():
        return None

    @staticmethod
    def default_output():
        return None


def _drive(monkeypatch, tmp_path, *, engine, decline_c=False):
    qa = tmp_path / "qa.yaml"
    qa.write_text(_QA, encoding="utf-8")
    monkeypatch.setenv("SPEAKLOOP_QA_FILE", str(qa))
    monkeypatch.setenv("SPEAKLOOP_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("SPEAKLOOP_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("SPEAKLOOP_HOME", str(tmp_path / "home"))

    phases: list[str] = []

    def _fake_ensure(phase, *, console=None, **kwargs):
        phases.append(phase)
        if decline_c and phase == "C":
            raise installer.InstallDeclinedError("declined")

    monkeypatch.setattr(installer, "ensure_models", _fake_ensure)

    with pytest.raises(typer.Exit) as exc:
        practice.run(
            question="q1",
            engine=engine,
            tts_engine=_StubTTS(),
            play_fn=lambda p: None,
            audio_devices=_NoMicDevices(),
        )
    return phases, exc.value.exit_code


def test_cloud_engine_never_provisions_local_llm(monkeypatch, tmp_path, capsys):
    phases, code = _drive(monkeypatch, tmp_path, engine="openrouter")
    assert "C" not in phases
    assert phases == ["B"]
    assert code == 1  # stopped at the (stubbed) missing-microphone check, not a download abort


def test_local_engine_provisions_local_llm(monkeypatch, tmp_path, capsys):
    phases, code = _drive(monkeypatch, tmp_path, engine="local")
    assert phases == ["B", "C"]
    assert code == 1


def test_declining_local_llm_degrades_not_aborts(monkeypatch, tmp_path, capsys):
    phases, code = _drive(monkeypatch, tmp_path, engine="local", decline_c=True)
    assert phases == ["B", "C"]  # the local LLM was offered...
    out = capsys.readouterr().out  # rich may wrap, so match short contiguous fragments
    assert "declined" in out and "record" in out  # ...declining degraded rather than aborting
    assert code == 1  # the run continued to the mic check (Exit 1), not an InstallDeclinedError
