"""T015/T016 (004) + T020 (007) — path-portability audit + HF token leak guard.

CI-only gates:
- No tracked file may contain a machine-specific absolute path
  (`/Users/<name>/`, `/home/<name>/`, `C:\\Users\\<name>\\`). Portable references
  — `~/...` and angle-bracket placeholders like `/Users/<name>/` — are NOT flagged.
- No tracked file outside `doc/` or `specs/` may contain a literal HuggingFace
  token (`hf_[A-Za-z0-9]{20,}`); the credential is consumed at runtime only
  (FR-013 / SC-006 / 007 token-resolution-contract.md §3).

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

# 007 (FR-013 / SC-006): literal HuggingFace tokens. The `hf_` prefix + ≥20
# trailing alphanumerics is the HF documented format; this scan runs everywhere
# except the design docs (`doc/`) and the per-feature spec tree (`specs/`),
# which may legitimately quote the pattern for reference. Test fixtures are
# also excluded — they are allowed to contain *placeholder* values such as
# `hf_envvalue_abc` that are intentionally short / clearly synthetic.
_HF_TOKEN_PATTERN = re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")
_HF_TOKEN_SCAN_EXCLUDE_PREFIXES = ("doc/", "specs/", "tests/")


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


def find_hf_token_leaks(repo_root: Path) -> list[str]:
    """Return sorted ``"<relpath>:<line>"`` strings for every literal HF token
    leak (`hf_<≥20 alphanumerics>`) found in tracked text files outside
    `doc/`, `specs/`, and `tests/`. Empty list == clean tree (007 FR-013)."""
    leaks: list[str] = []
    for path in _tracked_files(repo_root):
        if path.resolve() == _THIS_FILE:
            continue
        rel = path.relative_to(repo_root).as_posix()
        if rel.startswith(_HF_TOKEN_SCAN_EXCLUDE_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _HF_TOKEN_PATTERN.search(line):
                leaks.append(f"{rel}:{lineno}")
    return sorted(leaks)


def _is_hf_token(s: str) -> bool:
    return bool(_HF_TOKEN_PATTERN.search(s))


def test_repo_tree_has_no_absolute_path_leaks():
    """FR-010 / SC-B: the current tree is clean."""
    leaks = find_leaks(REPO_ROOT)
    assert leaks == [], "Machine-specific absolute-path leaks found:\n" + "\n".join(leaks)


def test_repo_tree_has_no_hf_token_leaks():
    """007 FR-013 / SC-006: no real / placeholder HF token is committed outside
    of the design docs and the spec tree."""
    leaks = find_hf_token_leaks(REPO_ROOT)
    assert leaks == [], "HuggingFace token leaks found:\n" + "\n".join(leaks)


def test_hf_token_detector_flags_real_looking_token():
    """Positive self-test: a 20+ char alphanumeric `hf_…` value is caught."""
    assert _is_hf_token("export HF_TOKEN=hf_abcdefghijklmnopqrstuvwxyz1234")
    assert _is_hf_token("# my token: hf_AAAAAAAAAAAAAAAAAAAAAA")


def test_hf_token_detector_ignores_short_placeholders():
    """Negative self-test: short synthetic stand-ins (used in test fixtures)
    do not match — they fall below the 20-char trailing-alphanumeric floor."""
    assert not _is_hf_token("hf_short")
    assert not _is_hf_token("hf_xyz")
    assert not _is_hf_token("hf_envvalue_abc")


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
