"""Shared CLI UX for the pronunciation RAM/engine safety gate (IMP-031).

Both `practice` (in-session drills) and `pronounce` (standalone) reach the same "unsafe → offer
the explicit freeze-warned override" prompt; this is the single copy so the wording can't drift
(it already had: "loading the pronunciation model" vs "loading the model"). The gate DECISION
(safe/unsafe + reason) is made in `speakloop.pronunciation` (`assess_safety` /
`assess_standalone_safety`); this module only renders the interactive consent.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from rich.console import Console


def is_interactive() -> bool:
    """Whether we can prompt the user (a real terminal on stdin). Re-exported by `practice` and
    `pronounce` as their `_is_interactive` test seam so tests can override it per module."""
    return sys.stdin.isatty()


def confirm_freeze_override(
    console: Console, *, input_fn: Callable[[str], str], interactive: bool
) -> bool:
    """Offer the explicit freeze-warned override for an UNSAFE pronunciation gate.

    Returns True when the user accepts loading the model despite the memory risk, False to skip.
    Non-interactive → False without prompting. `interactive` is passed in (computed by the
    caller's own `_is_interactive` seam) so tests keep driving it per module.
    """
    if not interactive:
        return False
    try:
        ans = input_fn(
            "Load the pronunciation model anyway? This may freeze your machine. [y/N]: "
        ).strip().lower()
    except EOFError:
        return False
    if ans in {"y", "yes"}:
        console.print(
            "[red]Override accepted — loading the pronunciation model despite the memory risk.[/red]"
        )
        return True
    return False
