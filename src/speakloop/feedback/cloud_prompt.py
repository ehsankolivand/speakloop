"""Cloud-mode system-prompt loader (feature 008).

The cloud system prompt lives in its OWN user-editable file
(``~/.speakloop/openrouter_prompt.txt``), seeded on first use from a packaged
default asset shipped beside this module. It is wholly separate from the local
flow's ``_SYSTEM_PROMPT`` (``grammar_analyzer.py``), which this module NEVER
reads or imports (FR-012). Editing the user file changes cloud behavior on the
next run with no code change (FR-011).
"""

from __future__ import annotations

from pathlib import Path

from speakloop.config import paths

# Packaged default, read the same way `coherence.py` reads `common_words.txt`.
_DEFAULT_ASSET = Path(__file__).parent / "openrouter_prompt_default.txt"


def load_cloud_prompt() -> tuple[str, Path]:
    """Return ``(prompt_text, user_path)``, seeding the user file if absent.

    On first use the packaged default is copied to
    ``paths.openrouter_prompt_path()`` so the editable surface is discoverable;
    thereafter the user's (possibly edited) file is read verbatim."""
    target = paths.openrouter_prompt_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_DEFAULT_ASSET.read_text(encoding="utf-8"), encoding="utf-8")
    return target.read_text(encoding="utf-8"), target
