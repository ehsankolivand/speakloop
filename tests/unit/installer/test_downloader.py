"""T009 (007) — downloader orchestration assertions.

Asserts:
- aria2 path uses the 8 pinned constants from contracts/downloader-cli-contract.md §8
- snapshot_download fallback path is taken when `shutil.which("aria2c")` is None,
  prints exactly one yellow warning, and the warning names `brew install aria2`
- transient outcome → respawn after 10 s sleep
- hard outcome → raise typed exception, no respawn

Caffeinate lifecycle assertions live in `tests/integration/test_caffeinate_lifecycle.py`
because, per contract §2, the wakelock is now scoped to `ensure_models(...)`, not
`download_model(...)`.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from speakloop.installer import (
    DownloadAuthError,
    downloader,
    manifest,
)
from speakloop.installer.aria import Aria2Outcome

pytestmark = pytest.mark.unit


# ----------------------------- helpers ------------------------------------ #


def _index_dir(local_dir: Path, shards: list[str]) -> None:
    """Pre-seed metadata index so discover_shards returns the expected shards."""
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "model.safetensors.index.json").write_text(
        json.dumps(
            {"weight_map": {f"layer.{i}": s for i, s in enumerate(shards)}}
        )
    )


class _RecordingProc:
    """Stand-in for `subprocess.Popen(caffeinate)` and `Popen(aria2)`."""

    def __init__(self, argv):
        self.argv = list(argv)
        self.terminated = False
        self.killed = False
        self.returncode = 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


def _patch_popen(monkeypatch, *, records: list):
    """Capture every Popen call. caffeinate gets a recording fake; anything else
    must not be used by `download_model` directly (aria.run is patched separately)."""
    import subprocess

    def _fake_popen(argv, *a, **kw):
        proc = _RecordingProc(argv)
        records.append(proc)
        return proc

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)


def _patch_curl_ok(monkeypatch):
    """Make every `subprocess.run` (curl) succeed without touching the network."""
    import subprocess

    def _fake_run(cmd, *a, **kw):
        # Honor `-o <path>` by creating an empty file so the curl-ok branch
        # mirrors a real successful fetch.
        if "-o" in cmd:
            i = cmd.index("-o")
            out_path = Path(cmd[i + 1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.touch()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)


# -------------------------- aria2 invocation ------------------------------ #


def test_aria2_invocation_pins_all_constants(monkeypatch, tmp_models_dir):
    """Per contracts/downloader-cli-contract.md §5 + §8."""
    procs: list[_RecordingProc] = []
    _patch_popen(monkeypatch, records=procs)
    _patch_curl_ok(monkeypatch)

    monkeypatch.setattr(downloader.shutil, "which", lambda _name: "/opt/homebrew/bin/aria2c")

    captured_cmds: list[list[str]] = []

    def _fake_aria_run(cmd, *, shard_filename, on_progress):
        captured_cmds.append(list(cmd))
        return Aria2Outcome.SUCCESS, None

    monkeypatch.setattr(downloader.aria, "run", _fake_aria_run)

    model = manifest.KOKORO_82M
    _index_dir(model.local_path, ["model.safetensors"])

    downloader.download_model(
        model,
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
    )

    assert captured_cmds, "aria.run was never invoked"
    cmd = captured_cmds[0]
    # The 8 pinned constants in contract §8.
    assert "--max-connection-per-server=16" in cmd
    assert "--split=16" in cmd
    assert "--min-split-size=1M" in cmd
    assert "--continue=true" in cmd
    assert "--max-tries=0" in cmd
    assert "--retry-wait=5" in cmd
    assert "--connect-timeout=30" in cmd
    # Output / dir / URL formatting.
    assert "--out=model.safetensors" in cmd
    assert f"--dir={model.local_path}" in cmd
    assert cmd[-1].startswith("https://huggingface.co/")
    assert cmd[-1].endswith("/resolve/main/model.safetensors")
    # No --header (anonymous default at this layer; US3 wires the token).
    assert not any(a.startswith("--header=") for a in cmd)


# ------------------------- snapshot_download fallback --------------------- #


def test_fallback_when_aria2_missing(monkeypatch, tmp_models_dir):
    procs: list[_RecordingProc] = []
    _patch_popen(monkeypatch, records=procs)

    # No aria2 on PATH.
    monkeypatch.setattr(downloader.shutil, "which", lambda _name: None)
    aria_calls = []
    monkeypatch.setattr(
        downloader.aria,
        "run",
        lambda *a, **kw: aria_calls.append((a, kw)) or (Aria2Outcome.SUCCESS, None),
    )

    captured = {}

    def _fake_snapshot(**kwargs):
        captured.update(kwargs)
        Path(kwargs["local_dir"]).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("huggingface_hub.snapshot_download", _fake_snapshot)

    sink = io.StringIO()
    console = Console(file=sink, force_terminal=False, width=200)

    model = manifest.KOKORO_82M
    downloader.download_model(model, console=console)

    out = sink.getvalue()
    assert "aria2" in out and "brew install aria2" in out
    # exactly one warning line about aria2 not found
    assert out.count("brew install aria2") == 1
    assert captured["repo_id"] == model.hf_repo_id
    assert captured["resume_download"] is True
    assert captured["token"] is None
    assert aria_calls == []  # aria path NOT taken


# --------------------------- retry semantics ------------------------------ #


def test_transient_failure_triggers_respawn_with_10s_sleep(monkeypatch, tmp_models_dir):
    procs: list[_RecordingProc] = []
    _patch_popen(monkeypatch, records=procs)
    _patch_curl_ok(monkeypatch)

    monkeypatch.setattr(downloader.shutil, "which", lambda _name: "/opt/homebrew/bin/aria2c")

    outcomes = iter(
        [
            (Aria2Outcome.TRANSIENT_FAILURE, None),
            (Aria2Outcome.TRANSIENT_FAILURE, None),
            (Aria2Outcome.SUCCESS, None),
        ]
    )

    aria_calls = {"n": 0}

    def _fake_aria(cmd, *, shard_filename, on_progress):
        aria_calls["n"] += 1
        return next(outcomes)

    monkeypatch.setattr(downloader.aria, "run", _fake_aria)

    sleeps: list[float] = []
    monkeypatch.setattr(downloader.time, "sleep", lambda s: sleeps.append(s))

    model = manifest.KOKORO_82M
    _index_dir(model.local_path, ["model.safetensors"])

    downloader.download_model(
        model,
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
    )

    assert aria_calls["n"] == 3
    # 2 transient retries → 2 sleeps of 10 s.
    assert sleeps.count(10) >= 2


def test_hard_failure_raises_without_respawn(monkeypatch, tmp_models_dir):
    procs: list[_RecordingProc] = []
    _patch_popen(monkeypatch, records=procs)
    _patch_curl_ok(monkeypatch)

    monkeypatch.setattr(downloader.shutil, "which", lambda _name: "/opt/homebrew/bin/aria2c")

    aria_calls = {"n": 0}

    def _fake_aria(cmd, *, shard_filename, on_progress):
        aria_calls["n"] += 1
        return Aria2Outcome.HARD_FAILURE, DownloadAuthError("auth")

    monkeypatch.setattr(downloader.aria, "run", _fake_aria)

    sleeps: list[float] = []
    monkeypatch.setattr(downloader.time, "sleep", lambda s: sleeps.append(s))

    model = manifest.KOKORO_82M
    _index_dir(model.local_path, ["model.safetensors"])

    with pytest.raises(DownloadAuthError):
        downloader.download_model(
            model,
            console=Console(file=io.StringIO(), force_terminal=False, width=120),
        )
    assert aria_calls["n"] == 1
    # No retry sleep should have run.
    assert all(s != 10 for s in sleeps), f"unexpected retry sleep: {sleeps}"


def _fetch_metadata_with_exit(monkeypatch, tmp_path, code):
    import subprocess

    from rich.console import Console

    from speakloop.installer import downloader
    from speakloop.installer.tokens import ResolvedToken

    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, *a, **kw: subprocess.CompletedProcess(args=cmd, returncode=code, stdout="", stderr=""),
    )
    console = Console(record=True, width=240)
    downloader._fetch_metadata(
        local_dir=tmp_path,
        base_url="https://example.test/repo/resolve/main",
        token=ResolvedToken(value=None, source="anonymous"),
        console=console,
    )
    return console.export_text()


def test_fetch_metadata_network_error_is_distinct_from_absence(monkeypatch, tmp_path):
    """IMP-028: a network-class curl exit (6 = couldn't resolve host) prints a distinct
    'network error' warning, NOT the misleading 'not in repo, skipping' absence message."""
    out = _fetch_metadata_with_exit(monkeypatch, tmp_path, 6)
    assert "network error" in out
    assert "not in repo, skipping" not in out


def test_fetch_metadata_absent_file_still_skips_quietly(monkeypatch, tmp_path):
    """A genuine absence (curl exit 22 = HTTP >= 400 under -f) keeps the quiet skip message."""
    out = _fetch_metadata_with_exit(monkeypatch, tmp_path, 22)
    assert "not in repo, skipping" in out
    assert "network error" not in out
