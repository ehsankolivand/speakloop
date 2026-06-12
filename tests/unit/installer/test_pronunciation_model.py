"""T031 (016) — the pronunciation model is fetched via the existing aria2 downloader.

Proves the model uses its explicit `weight_files` (pytorch_model.bin) instead of the
safetensors `discover_shards` fallback (which would 404), that `preprocessor_config.json`
is in META_FILES, and that `ensure_pronunciation_model` honors decline + reuses the
consent/download/validate lifecycle (no bespoke path).
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop import installer
from speakloop.installer import downloader, manifest
from speakloop.installer.aria import Aria2Outcome

pytestmark = pytest.mark.unit


def test_weight_files_set_and_not_in_any_phase():
    m = manifest.WAV2VEC2_PRONUNCIATION
    assert m.weight_files == ("pytorch_model.bin",)
    for lst in (manifest.PHASE_A_MODELS, manifest.PHASE_B_MODELS, manifest.PHASE_C_MODELS):
        assert m not in lst, "the pronunciation model must NOT be in a phase list (opt-in only)"


def test_preprocessor_config_in_meta_files():
    assert "preprocessor_config.json" in downloader.META_FILES


def _patch_curl_ok(monkeypatch):
    import subprocess
    from pathlib import Path

    def _fake_run(cmd, *a, **kw):
        if "-o" in cmd:
            out = Path(cmd[cmd.index("-o") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.touch()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)


def test_aria_uses_weight_files_not_safetensors(monkeypatch, tmp_models_dir):
    """The aria path must request pytorch_model.bin (from weight_files), proving
    discover_shards was bypassed — no model.safetensors is requested."""
    _patch_curl_ok(monkeypatch)
    monkeypatch.setattr(downloader.shutil, "which", lambda _n: "/opt/homebrew/bin/aria2c")

    captured: list[list[str]] = []

    def _fake_aria(cmd, *, shard_filename, on_progress):
        captured.append(list(cmd))
        return Aria2Outcome.SUCCESS, None

    monkeypatch.setattr(downloader.aria, "run", _fake_aria)

    # NOTE: deliberately do NOT pre-seed model.safetensors.index.json — if weight_files
    # were ignored, discover_shards would request "model.safetensors" here.
    downloader.download_model(
        manifest.WAV2VEC2_PRONUNCIATION,
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
    )

    outs = [a for cmd in captured for a in cmd if a.startswith("--out=")]
    assert "--out=pytorch_model.bin" in outs
    assert "--out=model.safetensors" not in outs


def test_ensure_pronunciation_model_honors_decline(monkeypatch, tmp_models_dir):
    download_calls = []

    def _record_download(m, *, console=None):
        download_calls.append(m)

    with pytest.raises(installer.InstallDeclinedError):
        installer.ensure_pronunciation_model(
            console=Console(file=io.StringIO(), force_terminal=False, width=120),
            consent_fn=lambda models, *, console, input_fn: False,
            download_fn=_record_download,
        )
    assert download_calls == [], "declining must not download anything"


def test_ensure_pronunciation_model_downloads_then_revalidates(monkeypatch, tmp_models_dir):
    state = {"downloaded": False}

    def _fake_validate(model):
        from speakloop.installer.validator import ValidationResult

        ok = state["downloaded"]
        return ValidationResult(ok=ok, reason="ok" if ok else "missing")

    monkeypatch.setattr(installer.validator, "validate", _fake_validate)

    def _fake_download(m, *, console=None):
        state["downloaded"] = True

    downloaded = []
    installer.ensure_pronunciation_model(
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
        consent_fn=lambda models, *, console, input_fn: True,
        download_fn=lambda m, *, console=None: (downloaded.append(m), _fake_download(m, console=console))[1],
    )
    assert downloaded and downloaded[0] is manifest.WAV2VEC2_PRONUNCIATION
