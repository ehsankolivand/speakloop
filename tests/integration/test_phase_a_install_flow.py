"""T031 — Phase A installer flow end-to-end with fakes."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from speakloop import installer

pytestmark = pytest.mark.integration


def _fake_download_factory(scratch_dir):
    """Fake downloader that writes a file matching expected_size_bytes via chunked writes."""

    CHUNK = 4 * 1024 * 1024  # 4 MiB
    chunk_bytes = b"x" * CHUNK

    def _fake(model, *, console=None):
        d = model.local_path
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "weights.bin", "wb") as f:
            remaining = model.expected_size_bytes
            while remaining > 0:
                n = min(CHUNK, remaining)
                f.write(chunk_bytes if n == CHUNK else b"x" * n)
                remaining -= n

    return _fake


def test_accept_downloads_and_validates(tmp_models_dir):
    fake_download = _fake_download_factory(tmp_models_dir)
    installer.ensure_models(
        "A",
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
        consent_fn=lambda models, console, input_fn: True,
        download_fn=fake_download,
    )
    # Re-call: should be a no-op (everything validates).
    installer.ensure_models(
        "A",
        console=Console(file=io.StringIO(), force_terminal=False, width=120),
        consent_fn=lambda *_a, **_k: pytest.fail("consent should not be asked twice"),
        download_fn=lambda *_a, **_k: pytest.fail("should not re-download"),
    )


def test_decline_raises_and_writes_nothing(tmp_models_dir):
    with pytest.raises(installer.InstallDeclinedError):
        installer.ensure_models(
            "A",
            console=Console(file=io.StringIO(), force_terminal=False, width=120),
            consent_fn=lambda *_a, **_k: False,
            download_fn=lambda *_a, **_k: pytest.fail("should not download"),
        )
    # Nothing should be written.
    assert list(tmp_models_dir.iterdir()) == []
