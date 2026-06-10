"""Follow-up prompt loader (010-interview-loop, P1).

Mirrors ``feedback.cloud_prompt``: the packaged default is seeded into a
user-editable file (``~/.speakloop/openrouter_followups_prompt.txt``) on first use
so it is a discoverable tuning surface, then read verbatim. Used in BOTH local and
cloud modes (the system prompt is engine-agnostic).
"""

from __future__ import annotations

from pathlib import Path

from speakloop.config import paths

_DEFAULT = Path(__file__).parent / "followups_prompt_default.txt"


def load_followups_prompt() -> tuple[str, Path]:
    """Return ``(prompt_text, user_path)``, seeding the user file if absent."""
    target = paths.openrouter_followups_prompt_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_DEFAULT.read_text(encoding="utf-8"), encoding="utf-8")
    return target.read_text(encoding="utf-8"), target
