"""T029 — downloader passes resume_download=True (FR-021, SC-002)."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop.installer import downloader, manifest

pytestmark = pytest.mark.unit


def test_passes_resume_download_true(monkeypatch, tmp_models_dir):
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        # Simulate creation of one file to look like a real download.
        (tmp_models_dir / kwargs["repo_id"].replace("/", "__")).mkdir(exist_ok=True)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    downloader.download_model(
        manifest.KOKORO_82M,
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
    )

    assert len(calls) == 1
    kw = calls[0]
    assert kw["repo_id"] == manifest.KOKORO_82M.hf_repo_id
    assert kw["resume_download"] is True
    assert kw["local_dir"]


def test_second_call_observes_existing_partial(monkeypatch, tmp_models_dir):
    observed = []

    def fake_snapshot_download(**kwargs):
        local_dir = kwargs["local_dir"]
        from pathlib import Path

        p = Path(local_dir)
        p.mkdir(parents=True, exist_ok=True)
        already = sorted(x.name for x in p.iterdir())
        observed.append(already)
        (p / "part.bin").write_bytes(b"x" * 1024)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    downloader.download_model(manifest.KOKORO_82M, console=console)
    downloader.download_model(manifest.KOKORO_82M, console=console)

    # First call: empty partial dir. Second call: previous file present.
    assert observed[0] == []
    assert "part.bin" in observed[1]
