"""HuggingFace token resolution (007).

Resolution order: `$HF_TOKEN` → `~/.cache/huggingface/token` → anonymous.

Contract: `specs/007-robust-model-download/contracts/token-resolution-contract.md`.

No-leak invariants:
- The token value never appears in `repr(ResolvedToken)`.
- Pure function: no logging, no exceptions on missing inputs, no writes to
  `os.environ` or anywhere else.
- Whitespace is stripped from file contents before non-emptiness is checked.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TokenSource = Literal["env", "hf_cli_file", "anonymous"]

_HF_CLI_TOKEN_PATH = "~/.cache/huggingface/token"


@dataclass(frozen=True)
class ResolvedToken:
    value: str | None
    source: TokenSource

    def __repr__(self) -> str:  # never include `value`
        return f"ResolvedToken(source={self.source!r}, value=<redacted>)"


def resolve_token() -> ResolvedToken:
    """Return the active HF token or `anonymous`. Never raises."""
    env_value = os.environ.get("HF_TOKEN", "").strip()
    if env_value:
        return ResolvedToken(value=env_value, source="env")

    file_path = Path(os.path.expanduser(_HF_CLI_TOKEN_PATH))
    try:
        if file_path.is_file():
            contents = file_path.read_text(encoding="utf-8").strip()
            if contents:
                return ResolvedToken(value=contents, source="hf_cli_file")
    except OSError:
        # Unreadable file → treat as anonymous; never raise from resolution.
        pass

    return ResolvedToken(value=None, source="anonymous")
