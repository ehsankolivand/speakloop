"""T041 — `speakloop --help` works with no models and loads no engine packages.

Constitution Principle VIII (and the cli/CLAUDE.md contract). Importing the CLI
must not pull in mlx_whisper / silero_vad / parakeet_mlx / mlx_lm / kokoro_mlx
at module load — those imports are function-local inside the wrapper files.
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
        "engine = {'mlx_whisper', 'silero_vad', 'parakeet_mlx', 'mlx_lm', 'kokoro_mlx', 'torch', 'transformers'}; "
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
        "engine = {'mlx_whisper', 'silero_vad', 'parakeet_mlx', 'mlx_lm', 'kokoro_mlx', 'torch', 'transformers'}; "
        "leaked = engine & set(sys.modules); "
        "print('LEAKED', sorted(leaked)); "
        "sys.exit(1 if leaked else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"engine packages loaded during --help: {proc.stdout}{proc.stderr}"


def test_practice_help_lists_cloud_flag():
    """008: the `--cloud` opt-in is discoverable and `practice --help` stays
    model-free."""
    result = CliRunner().invoke(app, ["practice", "--help"])
    assert result.exit_code == 0
    assert "--cloud" in result.output


def test_practice_help_lists_timings_flag():
    """012: the `--timings` flag is discoverable and `practice --help` stays model-free."""
    result = CliRunner().invoke(app, ["practice", "--help"])
    assert result.exit_code == 0
    assert "--timings" in result.output


def test_help_lists_deck_and_shadow():
    """018: the two self-practice modes are discoverable from the top-level help."""
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "deck" in result.output and "shadow" in result.output


def test_deck_and_shadow_help_stay_model_free():
    for cmd in ("deck", "shadow"):
        result = CliRunner().invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, result.output


def test_importing_deck_and_shadow_modules_loads_no_engine_packages():
    """018: the thin `cli/deck.py` + `cli/shadow.py` modules import engines function-local,
    so importing them (and the pure `linecards`/`shadowing`) pulls in no engine package."""
    code = (
        "import sys; import speakloop.cli.deck, speakloop.cli.shadow; "
        "import speakloop.linecards, speakloop.shadowing; "
        "engine = {'mlx_whisper', 'silero_vad', 'parakeet_mlx', 'mlx_lm', 'kokoro_mlx', 'torch', 'transformers'}; "
        "leaked = engine & set(sys.modules); "
        "print('LEAKED', sorted(leaked)); "
        "sys.exit(1 if leaked else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"engine packages imported via deck/shadow: {proc.stdout}{proc.stderr}"


def test_importing_openrouter_engine_loads_no_engine_packages():
    """008: the cloud engine is stdlib-only (urllib) — importing it must pull in
    none of the local engine packages, so the `--help` model-free guarantee holds
    even with the cloud path present."""
    code = (
        "import sys; import speakloop.llm.openrouter_engine; "
        "engine = {'mlx_whisper', 'silero_vad', 'parakeet_mlx', 'mlx_lm', 'kokoro_mlx', 'torch', 'transformers'}; "
        "leaked = engine & set(sys.modules); "
        "print('LEAKED', sorted(leaked)); "
        "sys.exit(1 if leaked else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"engine packages imported via openrouter_engine: {proc.stdout}{proc.stderr}"


def test_importing_grammar_analyzer_loads_no_engine_packages():
    """T-G5 (006): the json-repair swap must keep `mlx_lm` function-local. Importing the
    changed grammar_analyzer module must pull NO engine package — it depends only on the
    `speakloop.llm` interface (LLMEngine Protocol), never the Qwen wrapper at import time."""
    code = (
        "import sys; import speakloop.feedback.grammar_analyzer; "
        "import json_repair; "  # the new dep must import cleanly and offline
        "engine = {'mlx_whisper', 'silero_vad', 'parakeet_mlx', 'mlx_lm', 'kokoro_mlx', 'torch', 'transformers'}; "
        "leaked = engine & set(sys.modules); "
        "print('LEAKED', sorted(leaked)); "
        "sys.exit(1 if leaked else 0)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"engine packages imported via grammar_analyzer: {proc.stdout}{proc.stderr}"
