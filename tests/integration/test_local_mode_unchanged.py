"""008 / SC-001: the default (non-cloud) path is unchanged.

Without `--cloud`, building the grammar analyzer must touch neither the cloud
modules nor the local LLM engine package, and must read no OpenRouter token —
the offline/local experience is byte-for-byte as before.
"""

from __future__ import annotations

import inspect
import os
import subprocess
import sys

import pytest

from speakloop.cli import practice

pytestmark = pytest.mark.integration


def test_run_defaults_to_local_mode():
    # The opt-in is off by default.
    assert inspect.signature(practice.run).parameters["cloud"].default is False


def test_default_analyzer_build_touches_no_cloud_or_engine(tmp_path):
    """Fresh interpreter: local `_build_grammar_analyzer()` with the Qwen model
    absent returns None (Phase-B only, as before) and loads neither `mlx_lm` nor
    any OpenRouter cloud module — proving the default path is untouched."""
    code = (
        "import sys;"
        "from speakloop.cli import practice;"
        "ana = practice._build_grammar_analyzer();"
        "cloud = {m for m in ("
        "  'mlx_lm',"
        "  'speakloop.llm.openrouter_engine',"
        "  'speakloop.llm.openrouter_credentials',"
        "  'speakloop.llm.openrouter_config',"
        ") if m in sys.modules};"
        "print('ANALYZER', ana);"
        "print('LOADED', sorted(cloud));"
        "sys.exit(1 if (ana is not None or cloud) else 0)"
    )
    env = dict(
        os.environ,
        SPEAKLOOP_HOME=str(tmp_path),
        SPEAKLOOP_MODELS_DIR=str(tmp_path / "models"),  # empty → Qwen invalid → None
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
