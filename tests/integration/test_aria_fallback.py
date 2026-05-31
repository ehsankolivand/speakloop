"""T010 (007) — installer.ensure_models("A") falls back to snapshot_download when
aria2 is missing on PATH (FR-019).

Hermetic: `subprocess.Popen` is patched so the host's real `caffeinate` is
never spawned during the test.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from speakloop import installer
from speakloop.installer import downloader, manifest

pytestmark = pytest.mark.integration


class _FakeProc:
    def __init__(self, argv):
        self.argv = list(argv)
        self.terminated = False
        self.returncode = 0

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


def test_fallback_keeps_consent_and_validation_intact(monkeypatch, tmp_models_dir):
    monkeypatch.setattr(downloader.shutil, "which", lambda _name: None)

    # Hermetic: no real caffeinate.
    spawned: list[_FakeProc] = []

    def _fake_popen(argv, *a, **kw):
        p = _FakeProc(argv)
        spawned.append(p)
        return p

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    def _seed(model: manifest.Model) -> None:
        target = Path(model.local_path)
        target.mkdir(parents=True, exist_ok=True)
        with open(target / "weights.bin", "wb") as f:
            f.write(b"x" * model.expected_size_bytes)

    captured_kwargs: dict = {}

    def _fake_snapshot(**kwargs):
        captured_kwargs.update(kwargs)
        for m in manifest.PHASE_A_MODELS:
            if m.hf_repo_id == kwargs["repo_id"]:
                _seed(m)
                return
        raise AssertionError(f"unexpected repo {kwargs['repo_id']}")

    monkeypatch.setattr("huggingface_hub.snapshot_download", _fake_snapshot)

    sink = io.StringIO()
    console = Console(file=sink, force_terminal=False, width=200)

    consents = {"asked": 0}

    def _consent(models, console, input_fn):
        consents["asked"] += 1
        return True

    installer.ensure_models(
        "A",
        console=console,
        consent_fn=_consent,
    )

    out = sink.getvalue()
    assert consents["asked"] == 1, "consent must still be prompted under fallback"
    assert "brew install aria2" in out
    assert out.count("brew install aria2") == 1, "exactly one warning line"
    assert captured_kwargs["repo_id"] == manifest.PHASE_A_MODELS[0].hf_repo_id
    assert captured_kwargs["resume_download"] is True
    assert captured_kwargs["token"] is None

    # Caffeinate was spawned ONCE at ensure_models entry, and terminated.
    caffs = [p for p in spawned if p.argv and p.argv[0] == "caffeinate"]
    assert len(caffs) == 1, f"expected exactly 1 caffeinate spawn, got {len(caffs)}"
    assert caffs[0].terminated
