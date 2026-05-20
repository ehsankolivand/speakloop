"""T015/T016 (004) — path-portability audit (US3).

A CI-only gate: no tracked file may contain a machine-specific absolute path
(`/Users/<name>/`, `/home/<name>/`, `C:\\Users\\<name>\\`). Portable references —
`~/...` and angle-bracket placeholders like `/Users/<name>/` — are NOT flagged.

Stdlib + git only (FR-028). Contract: contracts/path-audit.md.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# repo root = tests/integration/<this file> → parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]

# The audit's own file is self-referential (it contains the patterns and synthetic
# test strings below), so it is excluded from the scan.
_THIS_FILE = Path(__file__).resolve()

# Machine-specific home-directory paths. The `[A-Za-z0-9._-]+` login segment
# deliberately excludes `<` and `>`, so documentation placeholders such as
# `/Users/<name>/` do not match (FR-009). `~/...` never starts with these prefixes.
_LEAK_PATTERNS = (
    re.compile(r"(?:/Users/|/home/)[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\"),
)


def _tracked_files(repo_root: Path) -> list[Path]:
    """Tracked files via `git ls-files -z`, sorted for determinism."""
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    ).stdout
    rels = [p for p in out.decode("utf-8").split("\0") if p]
    return sorted(repo_root / r for r in rels)


def find_leaks(repo_root: Path) -> list[str]:
    """Return sorted ``"<relpath>:<line>"`` strings for every machine-specific
    absolute-path leak in tracked, decodable text files. Empty list == clean tree."""
    leaks: list[str] = []
    for path in _tracked_files(repo_root):
        if path.resolve() == _THIS_FILE:
            continue  # self-reference: this file defines the patterns + test strings
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable → skip
        rel = path.relative_to(repo_root).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pat.search(line) for pat in _LEAK_PATTERNS):
                leaks.append(f"{rel}:{lineno}")
    return sorted(leaks)


def _is_leak(s: str) -> bool:
    return any(pat.search(s) for pat in _LEAK_PATTERNS)


def test_repo_tree_has_no_absolute_path_leaks():
    """FR-010 / SC-B: the current tree is clean."""
    leaks = find_leaks(REPO_ROOT)
    assert leaks == [], "Machine-specific absolute-path leaks found:\n" + "\n".join(leaks)


def test_detector_flags_concrete_login_paths():
    """Positive self-test (SC-B): a real-looking login path is caught."""
    assert _is_leak("models live at /Users/concreteuser/data/x")
    assert _is_leak("/home/somebody/project/file")
    assert _is_leak(r"C:\Users\someone\AppData\thing")


def test_detector_ignores_portable_references():
    """Negative self-test (FR-009): tilde + angle-bracket placeholders are not leaks."""
    assert not _is_leak("~/.speakloop/qa.yaml")
    assert not _is_leak("models under ~/.speakloop/models/")
    assert not _is_leak("/Users/<name>/x")
    assert not _is_leak("/home/<user>/x")
    assert not _is_leak(r"C:\Users\<name>\x")


def test_audit_is_fast():
    """FR-011 / SC-G: completes deterministically in under 2 seconds."""
    start = time.perf_counter()
    find_leaks(REPO_ROOT)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"audit took {elapsed:.2f}s (budget 2.0s)"
