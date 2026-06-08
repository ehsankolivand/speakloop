"""OpenRouter token resolution + storage (feature 008).

Pure precedence resolver (env > stored file > None) plus a ``0600`` writer. No
interactive prompting here — that lives in the CLI (UI stays in ``cli/``). No
I/O at import time. Mirrors ``installer/tokens.py`` (007): env beats file.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from speakloop.config import paths

_ENV_VAR = "OPENROUTER_API_KEY"


def token_path() -> Path:
    """The stored-token location (``~/.speakloop/openrouter_token``)."""
    return paths.openrouter_token_path()


def resolve_token() -> str | None:
    """Return the OpenRouter token by precedence, or ``None`` if not configured.

    Order (first match wins):
      1. ``OPENROUTER_API_KEY`` environment variable (empty is treated as unset);
      2. the stored file ``~/.speakloop/openrouter_token`` (stripped, non-empty);
      3. ``None`` so the caller can trigger the first-run prompt.
    """
    env = os.environ.get(_ENV_VAR, "").strip()
    if env:
        return env
    p = token_path()
    try:
        if p.exists():
            stored = p.read_text(encoding="utf-8").strip()
            if stored:
                return stored
    except OSError:
        return None
    return None


def store_token(value: str) -> Path:
    """Persist ``value`` to ``token_path()`` with mode ``0600``. Refuses empty.

    Returns the path written. The value is never logged."""
    token = (value or "").strip()
    if not token:
        raise ValueError("Refusing to store an empty OpenRouter token.")
    p = token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(token + "\n", encoding="utf-8")
    with contextlib.suppress(OSError):  # best-effort hardening
        p.chmod(0o600)
    return p
