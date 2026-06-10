"""Triage prompt loaders (010-interview-loop, P4).

Mirrors ``feedback.cloud_prompt``: the mishearing prompt is seeded into a
user-editable file (``~/.speakloop/openrouter_triage_prompt.txt``) on first use so
it is a discoverable tuning surface; the consistency-check prompt is an internal
correctness safety check, so it is read from its packaged default directly (not a
tuning surface). Both packaged defaults ship beside this module.
"""

from __future__ import annotations

from pathlib import Path

from speakloop.config import paths

_TRIAGE_DEFAULT = Path(__file__).parent / "triage_prompt_default.txt"
_CONSISTENCY_DEFAULT = Path(__file__).parent / "consistency_prompt_default.txt"


def load_triage_prompt() -> tuple[str, Path]:
    """Return ``(prompt_text, user_path)`` for the mishearing prompt, seeding it."""
    target = paths.openrouter_triage_prompt_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_TRIAGE_DEFAULT.read_text(encoding="utf-8"), encoding="utf-8")
    return target.read_text(encoding="utf-8"), target


def load_consistency_prompt() -> str:
    """Return the packaged consistency-check system prompt (read directly)."""
    return _CONSISTENCY_DEFAULT.read_text(encoding="utf-8")
