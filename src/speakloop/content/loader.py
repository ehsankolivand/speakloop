"""Q&A YAML loader. Surfaces file:line on parse error (FR-029) and entry id + field on schema error (FR-030)."""

from __future__ import annotations

from pathlib import Path

import yaml

from speakloop.content.schema import QAFile, QASchemaError, parse


class QALoadError(Exception):
    """Wraps both parse errors (with file:line) and schema errors (with entry id)."""


def load(path: Path) -> QAFile:
    """Load and validate a Q&A YAML file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise QALoadError(f"Q&A file not found: {path}") from e
    except OSError as e:
        raise QALoadError(f"Failed to read Q&A file {path}: {e}") from e

    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        # FR-029: surface file path + line number with remediation hint.
        line = None
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            line = e.problem_mark.line + 1
        prefix = f"{path}:{line}:" if line else f"{path}:"
        raise QALoadError(
            f"{prefix} YAML parse error: {e}\n"
            "Hint: fix the YAML syntax (check indentation, quoting, "
            "and that every key has a colon). See "
            "specs/001-v1-product-spec/contracts/content-schema.yaml "
            "for the expected schema."
        ) from e

    try:
        return parse(doc)
    except QASchemaError as e:
        # FR-030: name the entry id + missing field exactly.
        parts = [f"{path}:"]
        if e.entry_id:
            parts.append(f"entry id={e.entry_id!r}:")
        if e.missing_field:
            parts.append(f"missing required field {e.missing_field!r}.")
        parts.append(str(e))
        raise QALoadError(" ".join(parts)) from e
