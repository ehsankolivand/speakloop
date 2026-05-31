"""aria2c subprocess wrapper + progress-line parser + exit classifier (007).

Contracts:
  - `specs/007-robust-model-download/contracts/progress-bridge-contract.md`
  - `specs/007-robust-model-download/data-model.md §Aria2Progress / §Aria2Outcome`

Stdlib-only. The only file in the codebase that knows aria2's CLI shape.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from speakloop.installer import (
    DownloadAuthError,
    DownloadDiskError,
    DownloadNotFoundError,
)

# --------------------------------------------------------------------------- #
# Types                                                                       #
# --------------------------------------------------------------------------- #


class Aria2Outcome(Enum):
    SUCCESS = "success"
    TRANSIENT_FAILURE = "transient"
    HARD_FAILURE = "hard"


@dataclass(frozen=True)
class Aria2Progress:
    bytes_received: int
    bytes_total: int
    download_rate_bps: int
    eta_seconds: int | None
    shard_filename: str


# --------------------------------------------------------------------------- #
# Parsing                                                                     #
# --------------------------------------------------------------------------- #

# aria2's progress lines look like:
#   [#1a2b3c 1.5GiB/8.0GiB(18%) CN:16 SD:16 DL:6.4MiB ETA:1m45s]
# `SD:` and `ETA:` are optional in the field-observed variants.
_PROGRESS_RE = re.compile(
    r"\["
    r"#[0-9a-fA-F]+\s+"
    r"(?P<received>[\d.]+[KMGT]?i?B)"
    r"/"
    r"(?P<total>[\d.]+[KMGT]?i?B)"
    r"\(\s*(?P<percent>\d+)%\)\s+"
    r"CN:(?P<conn>\d+)\s+"
    r"(?:SD:\d+\s+)?"
    r"DL:(?P<rate>[\d.]+[KMGT]?i?B)"
    r"(?:\s+ETA:(?P<eta>[\dhms]+))?"
    r"\]"
)

_SIZE_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>[KMGT]?i?B)?$")

_SIZE_FACTORS = {
    "B": 1,
    "KB": 1000,
    "KiB": 1024,
    "MB": 1000**2,
    "MiB": 1024**2,
    "GB": 1000**3,
    "GiB": 1024**3,
    "TB": 1000**4,
    "TiB": 1024**4,
}

_ETA_RE = re.compile(r"^(?:(?P<h>\d+)h)?(?:(?P<m>\d+)m)?(?:(?P<s>\d+)s)?$")


def _parse_size(raw: str) -> int:
    """Parse aria2 size strings (`512B`, `1.5MiB`, `8GB`, …) to bytes.

    Tolerant: returns 0 for the empty / unparseable case so a single noisy line
    can't crash the read loop.
    """
    if raw is None:
        return 0
    s = raw.strip()
    m = _SIZE_RE.match(s)
    if not m:
        return 0
    value = float(m.group("value"))
    unit = m.group("unit") or "B"
    factor = _SIZE_FACTORS.get(unit, 1)
    return int(value * factor)


def _parse_eta(raw: str | None) -> int | None:
    """Parse aria2 ETA strings (`25s`, `1m45s`, `1h2m3s`) to seconds.

    Returns None when the input is None or unparseable.
    """
    if raw is None:
        return None
    m = _ETA_RE.match(raw.strip())
    if not m:
        return None
    h = int(m.group("h") or 0)
    mnt = int(m.group("m") or 0)
    s = int(m.group("s") or 0)
    total = h * 3600 + mnt * 60 + s
    if total == 0 and not raw.endswith("0s"):
        return None
    return total


def _parse_progress(line: str, *, shard_filename: str) -> Aria2Progress | None:
    """Parse one aria2 stdout line into an Aria2Progress snapshot, or None."""
    if not line:
        return None
    m = _PROGRESS_RE.search(line)
    if not m:
        return None
    return Aria2Progress(
        bytes_received=_parse_size(m.group("received")),
        bytes_total=_parse_size(m.group("total")),
        download_rate_bps=_parse_size(m.group("rate")),
        eta_seconds=_parse_eta(m.group("eta")),
        shard_filename=shard_filename,
    )


# --------------------------------------------------------------------------- #
# Exit-code classifier (FR-005: hard errors must NOT be swallowed by retry)   #
# --------------------------------------------------------------------------- #


_TRANSIENT_EXIT_CODES = {1, 5, 6, 7}


def _classify_exit(
    exit_code: int,
    tail_lines: list[str],
) -> tuple[Aria2Outcome, Exception | None]:
    """Map an aria2 exit code + recent log lines to an Aria2Outcome.

    See data-model.md §Aria2Outcome for the rule table.
    """
    if exit_code == 0:
        return Aria2Outcome.SUCCESS, None

    if exit_code == 22:
        # HTTP error — peek the tail to decide auth vs not-found.
        haystack = "\n".join(tail_lines).lower()
        if "401" in haystack or "403" in haystack or "authorization failed" in haystack:
            return Aria2Outcome.HARD_FAILURE, DownloadAuthError(
                "HuggingFace returned 401/403; check $HF_TOKEN or "
                "~/.cache/huggingface/token, or fetch a public model."
            )
        if "404" in haystack or "not found" in haystack:
            return Aria2Outcome.HARD_FAILURE, DownloadNotFoundError(
                "HuggingFace returned 404; the repo or shard filename is wrong."
            )
        # Unknown HTTP failure — treat as hard so the user sees it.
        return Aria2Outcome.HARD_FAILURE, DownloadNotFoundError(
            "HuggingFace HTTP error (aria2 exit 22)."
        )

    if exit_code == 9:
        return Aria2Outcome.HARD_FAILURE, DownloadDiskError(
            "aria2 reports disk write failure (exit 9 — likely out of space)."
        )

    if exit_code in _TRANSIENT_EXIT_CODES:
        return Aria2Outcome.TRANSIENT_FAILURE, None

    # Conservative default — let the outer loop retry.
    return Aria2Outcome.TRANSIENT_FAILURE, None


# --------------------------------------------------------------------------- #
# Subprocess driver                                                           #
# --------------------------------------------------------------------------- #


_TAIL_LINES = 80  # how many recent log lines feed the exit classifier


def run(
    cmd: list[str],
    *,
    shard_filename: str,
    on_progress: Callable[[Aria2Progress], None],
) -> tuple[Aria2Outcome, Exception | None]:
    """Run `aria2c` once, stream progress, classify the outcome.

    The caller drives the outer indefinite-retry loop (contract §5).
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    tail: list[str] = []
    assert proc.stdout is not None  # for type-checkers
    try:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            tail.append(line)
            if len(tail) > _TAIL_LINES:
                tail = tail[-_TAIL_LINES:]
            snapshot = _parse_progress(line, shard_filename=shard_filename)
            if snapshot is not None:
                on_progress(snapshot)
    finally:
        proc.stdout.close()
        proc.wait()

    return _classify_exit(proc.returncode, tail)
