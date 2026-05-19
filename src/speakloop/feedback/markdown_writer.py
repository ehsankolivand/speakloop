"""Atomic Markdown write — temp file + os.replace (FR-016, SC-005, research.md)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_atomic(path: Path, content: str) -> None:
    """Write `content` to `path` atomically.

    Writes to a `<path>.tmp` sibling first, then `os.replace`s into place.
    A crash between buffer-flush and rename leaves only the `.tmp`.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # leave .tmp on disk — abort handler will sweep
        raise


def next_available_path(base_dir: Path, date_str: str, question_id: str) -> Path:
    """Filename-collision disambiguation per FR-017.

    `YYYY-MM-DD-<question_id>.md`, then `…-q<id>-2.md`, `-3.md`, …
    """
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    primary = base_dir / f"{date_str}-{question_id}.md"
    if not primary.exists():
        return primary
    n = 2
    while True:
        candidate = base_dir / f"{date_str}-{question_id}-{n}.md"
        if not candidate.exists():
            return candidate
        n += 1
