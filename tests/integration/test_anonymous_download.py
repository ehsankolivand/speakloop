"""T019 (007) — anonymous mode emits no Authorization header on curl / aria2c,
and prints no "Using HuggingFace token from …" diagnostic line.

FR-010 / SC-003 / token-resolution-contract.md §5.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from rich.console import Console

from speakloop.installer import downloader, manifest
from speakloop.installer.aria import Aria2Outcome

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


def test_anonymous_curl_and_aria_have_no_auth_header(
    monkeypatch,
    tmp_models_dir,
    tmp_path,
):
    # Force `~/.cache/huggingface/token` to a guaranteed-absent path.
    fake_home = tmp_path / "no_home"
    fake_home.mkdir()
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda p: p.replace("~", str(fake_home)),
    )
    monkeypatch.delenv("HF_TOKEN", raising=False)

    # aria2c "found" so we exercise the aria2 path, not fallback.
    monkeypatch.setattr(downloader.shutil, "which", lambda _name: "/opt/homebrew/bin/aria2c")

    # Capture every subprocess.run (curl) and subprocess.Popen (caffeinate).
    import subprocess

    curl_cmds: list[list[str]] = []

    def _fake_run(cmd, *a, **kw):
        curl_cmds.append(list(cmd))
        if "-o" in cmd:
            i = cmd.index("-o")
            Path(cmd[i + 1]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[i + 1]).touch()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    popen_calls: list[_FakeProc] = []

    def _fake_popen(argv, *a, **kw):
        p = _FakeProc(argv)
        popen_calls.append(p)
        return p

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    aria_cmds: list[list[str]] = []

    def _fake_aria_run(cmd, *, shard_filename, on_progress):
        aria_cmds.append(list(cmd))
        return Aria2Outcome.SUCCESS, None

    monkeypatch.setattr(downloader.aria, "run", _fake_aria_run)

    model = manifest.KOKORO_82M
    model.local_path.mkdir(parents=True, exist_ok=True)
    (model.local_path / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {"x": "model.safetensors"}})
    )

    sink = io.StringIO()
    console = Console(file=sink, force_terminal=False, width=200)

    downloader.download_model(model, console=console)

    out = sink.getvalue()
    # No diagnostic line — anonymous prints nothing about credentials.
    assert "Using HuggingFace token" not in out

    # No curl invocation carries an Authorization header.
    for cmd in curl_cmds:
        joined = " ".join(cmd)
        assert "Authorization:" not in joined, f"leaked auth in curl: {cmd}"

    # No aria2c invocation carries an Authorization header.
    for cmd in aria_cmds:
        assert not any(a.startswith("--header=Authorization") for a in cmd), (
            f"leaked auth in aria2: {cmd}"
        )
