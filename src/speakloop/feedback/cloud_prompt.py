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
# Packaged default for the cloud coaching prompt (009 — its OWN content).
_DEFAULT_COACH_ASSET = Path(__file__).parent / "openrouter_coach_prompt_default.txt"


def load_cloud_prompt() -> tuple[str, Path]:
    """Return ``(prompt_text, user_path)``, seeding the user file if absent.

    On first use the packaged default is copied to
    ``paths.openrouter_prompt_path()`` so the editable surface is discoverable;
    thereafter the user's (possibly edited) file is read verbatim."""
    return paths.seed_and_read(paths.openrouter_prompt_path(), _DEFAULT_ASSET)


def load_coach_prompt() -> tuple[str, Path]:
    """Return ``(prompt_text, user_path)`` for the cloud coaching prompt (009).

    Parallel to :func:`load_cloud_prompt`: on first use the packaged coach
    default is copied to ``paths.openrouter_coach_prompt_path()`` so the editable
    surface is discoverable; thereafter the user's (possibly edited) file is read
    verbatim and sent as the coach system prompt. The caller prints the returned
    path once so the user knows where to tune the teaching section. Wholly
    separate from the grammar prompt and from the local ``_SYSTEM_PROMPT``."""
    return paths.seed_and_read(paths.openrouter_coach_prompt_path(), _DEFAULT_COACH_ASSET)
