"""T008 (007) — aria2 progress parser + exit classifier.

Contract: `contracts/progress-bridge-contract.md §2-§4`;
data-model.md §Aria2Progress / §Aria2Outcome.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from speakloop.installer import (
    DownloadAuthError,
    DownloadDiskError,
    DownloadNotFoundError,
)
from speakloop.installer.aria import (
    Aria2Outcome,
    _classify_exit,
    _parse_eta,
    _parse_progress,
    _parse_size,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures" / "aria2_output"


def _load(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


# ---------------------------- _parse_size --------------------------------- #


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0B", 0),
        ("512B", 512),
        ("1KiB", 1024),
        ("1KB", 1000),
        ("1MiB", 1024 * 1024),
        ("1.5MiB", int(1.5 * 1024 * 1024)),
        ("8.0GiB", 8 * 1024**3),
        ("8GiB", 8 * 1024**3),
        ("170MiB", 170 * 1024**2),
    ],
)
def test_parse_size_units(raw, expected):
    assert _parse_size(raw) == expected


# ----------------------------- _parse_eta --------------------------------- #


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("25s", 25),
        ("1m45s", 60 + 45),
        ("1h2m3s", 3600 + 120 + 3),
        ("2h", 7200),
        (None, None),
    ],
)
def test_parse_eta(raw, expected):
    assert _parse_eta(raw) == expected


# --------------------------- _parse_progress ------------------------------ #


def test_parse_progress_typical_line():
    line = "[#1a2b3c 1.5GiB/8.0GiB(18%) CN:16 SD:16 DL:6.4MiB ETA:1m45s]"
    snap = _parse_progress(line, shard_filename="model.safetensors")
    assert snap is not None
    assert snap.bytes_received == int(1.5 * 1024**3)
    assert snap.bytes_total == 8 * 1024**3
    assert snap.download_rate_bps == int(6.4 * 1024**2)
    assert snap.eta_seconds == 60 + 45
    assert snap.shard_filename == "model.safetensors"


def test_parse_progress_returns_none_for_non_progress_line():
    for noise in (
        "",
        "Download Results:",
        "12/01 14:23:01 [NOTICE] Downloading 1 item(s)",
        "gid   |stat|avg speed  |path/URI",
    ):
        assert _parse_progress(noise, shard_filename="x") is None


def test_normal_run_fixture_yields_monotonic_progress():
    snaps = [
        s
        for s in (_parse_progress(line, shard_filename="model.safetensors") for line in _load("normal_run.txt"))
        if s is not None
    ]
    assert len(snaps) >= 5
    received = [s.bytes_received for s in snaps]
    assert received == sorted(received), "received bytes must be monotonic-nondecreasing"
    assert snaps[-1].bytes_received == snaps[-1].bytes_total  # finished


def test_resume_run_fixture_starts_above_zero():
    snaps = [
        s
        for s in (_parse_progress(line, shard_filename="model.safetensors") for line in _load("resume_run.txt"))
        if s is not None
    ]
    assert snaps
    assert snaps[0].bytes_received > 0, "resume run must start at a non-zero offset"


def test_missing_eta_fixture_yields_none_eta_for_early_lines():
    snaps = [
        s
        for s in (_parse_progress(line, shard_filename="model.safetensors") for line in _load("missing_eta.txt"))
        if s is not None
    ]
    assert snaps
    # Several initial lines must have no ETA.
    assert any(s.eta_seconds is None for s in snaps)


def test_transient_drop_fixture_keeps_yielding_progress_after_error_line():
    snaps = [
        s
        for s in (_parse_progress(line, shard_filename="model.safetensors") for line in _load("transient_drop.txt"))
        if s is not None
    ]
    # Has snapshots before AND after the error line.
    assert len(snaps) >= 4


# --------------------------- _classify_exit ------------------------------- #


def test_classify_exit_success():
    outcome, err = _classify_exit(0, _load("normal_run.txt"))
    assert outcome is Aria2Outcome.SUCCESS
    assert err is None


def test_classify_exit_transient_network():
    for code in (1, 5, 6, 7):
        outcome, err = _classify_exit(code, _load("transient_drop.txt"))
        assert outcome is Aria2Outcome.TRANSIENT_FAILURE
        assert err is None


def test_classify_exit_hard_auth_401():
    outcome, err = _classify_exit(22, _load("hard_auth.txt"))
    assert outcome is Aria2Outcome.HARD_FAILURE
    assert isinstance(err, DownloadAuthError)


def test_classify_exit_hard_404():
    outcome, err = _classify_exit(22, _load("hard_404.txt"))
    assert outcome is Aria2Outcome.HARD_FAILURE
    assert isinstance(err, DownloadNotFoundError)


def test_classify_exit_disk_full():
    outcome, err = _classify_exit(9, _load("disk_full.txt"))
    assert outcome is Aria2Outcome.HARD_FAILURE
    assert isinstance(err, DownloadDiskError)


def test_classify_exit_unknown_code_treated_as_transient():
    outcome, err = _classify_exit(99, [])
    assert outcome is Aria2Outcome.TRANSIENT_FAILURE
    assert err is None
