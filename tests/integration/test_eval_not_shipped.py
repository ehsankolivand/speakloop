"""T-E3 — `eval/` is a validation artifact, never shipped (eval-set-format Test obligations).

The wheel is scoped to `src/speakloop`; nothing under `eval/` may be imported by the
package at runtime, and no `src/speakloop` source may reference the eval harness. Mirrors
the engine-import isolation guard (root CLAUDE.md trap 2) for the eval directory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PKG = REPO_ROOT / "src" / "speakloop"
EVAL_DIR = REPO_ROOT / "eval"


def test_eval_dir_is_outside_the_package():
    assert EVAL_DIR.is_dir(), "eval/ should exist at the repo root"
    # eval/ must NOT live under the shipped package.
    assert not (SRC_PKG / "eval").exists()
    assert SRC_PKG.resolve() not in EVAL_DIR.resolve().parents


def test_wheel_is_scoped_to_the_package_only():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore
    data = tomllib.loads(text)
    packages = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert packages == ["src/speakloop"], packages


def test_no_package_source_imports_the_eval_harness():
    """No file under src/speakloop may import run_eval or reference eval/grammar."""
    offenders: list[str] = []
    needles = ("import run_eval", "from eval", "eval.grammar", "eval/grammar", "run_eval")
    for py in SRC_PKG.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if any(n in line for n in needles):
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{lineno}: {stripped}")
    assert offenders == [], "package source references the eval harness:\n" + "\n".join(offenders)


def test_importing_cli_loads_no_eval_module():
    """A fresh import of the CLI must not pull any module whose file lives in eval/."""
    code = (
        "import sys; import speakloop.cli.main; "
        "evald = []; "
        "import os.path as _p; "
        "from pathlib import Path as _P; "
        "evroot = _P(r'" + str(EVAL_DIR) + "').resolve(); "
        "leaked = ['run_eval'] if 'run_eval' in sys.modules else []; "
        "leaked += [n for n,m in list(sys.modules.items()) "
        "  if getattr(m,'__file__',None) and evroot in _P(m.__file__).resolve().parents]; "
        "print('LEAKED', sorted(set(leaked))); "
        "sys.exit(1 if leaked else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"eval module imported at CLI load: {proc.stdout}{proc.stderr}"
