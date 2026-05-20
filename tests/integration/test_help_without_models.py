"""T041 — `speakloop --help` works with no models and loads no engine packages.

Constitution Principle VIII (and the cli/CLAUDE.md contract). Importing the CLI
must not pull in mlx_whisper / silero_vad / parakeet_mlx / mlx_lm at module load
— those imports are function-local inside the wrapper files.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from speakloop.cli.main import app

pytestmark = pytest.mark.integration


def test_help_succeeds_and_lists_practice():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "practice" in result.output


def test_importing_cli_loads_no_engine_packages():
    # Fresh interpreter so the check is not polluted by other tests' imports.
    code = (
        "import sys; import speakloop.cli.main; "
        "engine = {'mlx_whisper', 'silero_vad', 'parakeet_mlx', 'mlx_lm'}; "
        "leaked = engine & set(sys.modules); "
        "print('LEAKED', sorted(leaked)); "
        "sys.exit(1 if leaked else 0)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"engine packages imported at CLI load: {proc.stdout}{proc.stderr}"


def test_help_does_not_load_engine_packages_during_invocation():
    code = (
        "import sys; from typer.testing import CliRunner; from speakloop.cli.main import app; "
        "r = CliRunner().invoke(app, ['practice', '--help']); "
        "assert r.exit_code == 0, r.output; "
        "engine = {'mlx_whisper', 'silero_vad', 'parakeet_mlx'}; "
        "leaked = engine & set(sys.modules); "
        "print('LEAKED', sorted(leaked)); "
        "sys.exit(1 if leaked else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"engine packages loaded during --help: {proc.stdout}{proc.stderr}"
