"""T011 (007) — caffeinate is spawned ONCE at `ensure_models(...)` entry, BEFORE
the consent prompt, and terminated in `finally` on every exit path:
success, decline (`InstallDeclinedError`), `InstallFailedError`, and any
unhandled exception.

Per `contracts/downloader-cli-contract.md §2`. No real caffeinate spawn —
`subprocess.Popen` is patched.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from rich.console import Console

from speakloop import installer
from speakloop.installer import (
    InstallDeclinedError,
    InstallFailedError,
    downloader,
    manifest,
)

pytestmark = pytest.mark.integration


class _FakeProc:
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


def _patch_popen(monkeypatch, records: list):
    import subprocess

    def _fake_popen(argv, *a, **kw):
        p = _FakeProc(argv)
        records.append(p)
        return p

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)


def _consent_yes(models, console, input_fn):
    return True


def _consent_no(models, console, input_fn):
    return False


def _seed_model_ok(model: manifest.Model) -> None:
    """Write enough bytes under model.local_path that validator.validate(...) == True."""
    target = Path(model.local_path)
    target.mkdir(parents=True, exist_ok=True)
    with open(target / "weights.bin", "wb") as f:
        f.write(b"x" * model.expected_size_bytes)


def _caffeinate_procs(procs: list[_FakeProc]) -> list[_FakeProc]:
    return [p for p in procs if p.argv and p.argv[0] == "caffeinate"]


# --------------------------------------------------------------------------- #
# caffeinate is the FIRST Popen call, BEFORE consent                          #
# --------------------------------------------------------------------------- #


def test_caffeinate_spawned_before_consent(monkeypatch, tmp_models_dir):
    procs: list[_FakeProc] = []
    _patch_popen(monkeypatch, procs)

    consent_order: list[str] = []

    def _consent(models, console, input_fn):
        # Record that, by the time consent runs, caffeinate is already spawned.
        consent_order.append("consent")
        return False  # decline so we don't proceed to download

    def _download(*a, **kw):
        pytest.fail("download must not run when consent declines")

    with pytest.raises(InstallDeclinedError):
        installer.ensure_models(
            "A",
            console=Console(file=io.StringIO(), force_terminal=False, width=120),
            consent_fn=_consent,
            download_fn=_download,
        )

    caffs = _caffeinate_procs(procs)
    assert caffs, "caffeinate was not spawned at ensure_models entry"
    first = caffs[0]
    assert "-dimsu" in first.argv
    assert "-w" in first.argv
    assert first.argv[first.argv.index("-w") + 1] == str(os.getpid())
    assert consent_order == ["consent"], "consent did not run"


# --------------------------------------------------------------------------- #
# caffeinate terminated on each exit path                                     #
# --------------------------------------------------------------------------- #


def test_caffeinate_terminated_on_success(monkeypatch, tmp_models_dir):
    procs: list[_FakeProc] = []
    _patch_popen(monkeypatch, procs)

    def _download(model, *, console=None):
        _seed_model_ok(model)

    installer.ensure_models(
        "A",
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
        consent_fn=_consent_yes,
        download_fn=_download,
    )

    caffs = _caffeinate_procs(procs)
    assert caffs and caffs[0].terminated


def test_caffeinate_terminated_on_decline(monkeypatch, tmp_models_dir):
    procs: list[_FakeProc] = []
    _patch_popen(monkeypatch, procs)

    with pytest.raises(InstallDeclinedError):
        installer.ensure_models(
            "A",
            console=Console(file=io.StringIO(), force_terminal=False, width=120),
            consent_fn=_consent_no,
            download_fn=lambda *a, **kw: pytest.fail("must not download"),
        )

    caffs = _caffeinate_procs(procs)
    assert caffs and caffs[0].terminated


def test_caffeinate_terminated_on_install_failed(monkeypatch, tmp_models_dir):
    """download_fn that does NOT write the model -> validator fails -> InstallFailedError."""
    procs: list[_FakeProc] = []
    _patch_popen(monkeypatch, procs)

    def _download_noop(*a, **kw):
        # do nothing — model directory stays empty, validator will fail
        return

    with pytest.raises(InstallFailedError):
        installer.ensure_models(
            "A",
            console=Console(file=io.StringIO(), force_terminal=False, width=120),
            consent_fn=_consent_yes,
            download_fn=_download_noop,
        )

    caffs = _caffeinate_procs(procs)
    assert caffs and caffs[0].terminated


def test_caffeinate_terminated_on_unexpected_exception(monkeypatch, tmp_models_dir):
    procs: list[_FakeProc] = []
    _patch_popen(monkeypatch, procs)

    def _boom(*a, **kw):
        raise RuntimeError("unexpected")

    with pytest.raises(RuntimeError):
        installer.ensure_models(
            "A",
            console=Console(file=io.StringIO(), force_terminal=False, width=120),
            consent_fn=_consent_yes,
            download_fn=_boom,
        )

    caffs = _caffeinate_procs(procs)
    assert caffs and caffs[0].terminated


# --------------------------------------------------------------------------- #
# Idempotency: when no model is missing, caffeinate is NOT spawned at all.    #
# --------------------------------------------------------------------------- #


def test_no_caffeinate_when_nothing_to_install(monkeypatch, tmp_models_dir):
    procs: list[_FakeProc] = []
    _patch_popen(monkeypatch, procs)

    # Pre-seed every Phase A model so `_missing_or_invalid` returns [].
    for m in manifest.PHASE_A_MODELS:
        _seed_model_ok(m)

    installer.ensure_models(
        "A",
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
        consent_fn=lambda *a, **kw: pytest.fail("must not ask consent"),
        download_fn=lambda *a, **kw: pytest.fail("must not download"),
    )

    assert _caffeinate_procs(procs) == [], (
        "caffeinate must not spawn when nothing is missing — that would burn a "
        "wakelock on every speakloop startup"
    )


# --------------------------------------------------------------------------- #
# Caffeinate is NOT spawned a second time inside download_model               #
# --------------------------------------------------------------------------- #


def test_download_model_does_not_spawn_a_second_caffeinate(monkeypatch, tmp_models_dir):
    """Per contract §2, the single wakelock is held by ensure_models, not by
    download_model. download_model called directly must not spawn its own."""
    procs: list[_FakeProc] = []
    _patch_popen(monkeypatch, procs)

    monkeypatch.setattr(downloader.shutil, "which", lambda _name: None)

    def _fake_snapshot(**kwargs):
        Path(kwargs["local_dir"]).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("huggingface_hub.snapshot_download", _fake_snapshot)

    downloader.download_model(
        manifest.KOKORO_82M,
        console=Console(file=io.StringIO(), force_terminal=False, width=200),
    )

    assert _caffeinate_procs(procs) == [], (
        "download_model must not spawn caffeinate — ensure_models owns the wakelock"
    )
