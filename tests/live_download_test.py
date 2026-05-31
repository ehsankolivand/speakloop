"""T016 (007) — live aria2 smoke test (opt-in, network required).

Mirrors the existing `live_asr` / `live_llm` pattern. Excluded from the default
suite via the `live_download` marker. Runs ONE small public artifact through
the real `downloader.download_model(...)` path.

Per `contracts/progress-bridge-contract.md §7`.
"""

from __future__ import annotations

import io
import shutil
import urllib.request

import pytest
from rich.console import Console

from speakloop.installer import downloader, manifest

pytestmark = pytest.mark.live_download


def test_real_aria2_pulls_a_small_public_artifact(tmp_models_dir):
    if shutil.which("aria2c") is None:
        pytest.skip("aria2c not on PATH — install with `brew install aria2`")

    # Pick the smallest model in the manifest so we are not burning bandwidth.
    model = manifest.KOKORO_82M

    # Capture HTTP `Content-Length` for one of the metadata files we expect
    # to fetch (config.json is always present on this repo).
    probe_url = f"https://huggingface.co/{model.hf_repo_id}/resolve/main/config.json"
    with urllib.request.urlopen(probe_url) as resp:  # noqa: S310 — public HF URL
        expected_len = int(resp.headers["Content-Length"])

    downloader.download_model(
        model,
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
    )

    fetched = (model.local_path / "config.json")
    assert fetched.exists(), "config.json was not fetched"
    assert fetched.stat().st_size == expected_len, (
        f"config.json size mismatch: got {fetched.stat().st_size}, "
        f"HTTP Content-Length was {expected_len}"
    )
