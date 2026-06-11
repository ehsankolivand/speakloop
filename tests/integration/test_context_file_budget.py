"""Guard: every CLAUDE.md stays within the 200-line context budget.

Owner of rule O17 (specs/014-agent-context-overhaul/research.md). The budget comes
from doc/research_context_engineering.md ("files over 200 lines consume more context
and may reduce adherence"). If this test fails, trim the offending file or move
detail into the owning module file / .claude/rules/ — never raise the budget.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

MAX_LINES = 200

REPO_ROOT = Path(__file__).resolve().parents[2]


def _tracked_claude_md_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "*CLAUDE.md", "**/CLAUDE.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        paths = [REPO_ROOT / line for line in out.splitlines() if line.strip()]
        if paths:
            return paths
    except (OSError, subprocess.CalledProcessError):
        pass
    # Fallback when git is unavailable: walk the tree, skipping virtualenvs.
    return [
        p
        for p in REPO_ROOT.rglob("CLAUDE.md")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]


def test_every_claude_md_is_within_line_budget() -> None:
    files = _tracked_claude_md_files()
    assert files, "expected at least the root CLAUDE.md to exist"
    over_budget = []
    for path in files:
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > MAX_LINES:
            over_budget.append(f"{path.relative_to(REPO_ROOT)}: {count} lines")
    assert not over_budget, (
        "CLAUDE.md files exceed the 200-line context budget "
        f"(doc/research_context_engineering.md): {'; '.join(over_budget)}"
    )
