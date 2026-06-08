"""OpenRouter model-id resolution from ``~/.speakloop/openrouter.yaml`` (008).

The single cloud setting is the ``model:`` key. It is read HERE (in the ``llm``
module) rather than in ``config/paths.py`` so the ``config`` leaf stays
stdlib-only (its CLAUDE.md forbids I/O beyond ``mkdir``). ``pyyaml`` is already a
project dependency (used by the question loader), so this adds no new dependency.

Absent file, absent/empty ``model:`` key, or malformed YAML all degrade to the
pinned default — resolution never raises (clarified Session 2026-06-08).
"""

from __future__ import annotations

import yaml

from speakloop.config import paths

DEFAULT_MODEL = "qwen/qwen3.7-max"


def resolve_model() -> str:
    """Return the configured OpenRouter model id, or ``DEFAULT_MODEL``."""
    p = paths.openrouter_config_path()
    try:
        if not p.exists():
            return DEFAULT_MODEL
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return DEFAULT_MODEL
    if isinstance(data, dict):
        model = data.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return DEFAULT_MODEL
