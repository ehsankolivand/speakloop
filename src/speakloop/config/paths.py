"""Filesystem-path constants. Single source of truth (Constitution Non-Negotiable)."""

from __future__ import annotations

import os
from pathlib import Path

_models_dir_override: Path | None = None
_sessions_dir_override: Path | None = None
_qa_file_override: Path | None = None


def _xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share"


def _xdg_cache_home() -> Path:
    raw = os.environ.get("XDG_CACHE_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".cache"


def _speakloop_home() -> Path:
    raw = os.environ.get("SPEAKLOOP_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".speakloop"


def set_models_dir(path: Path | None) -> None:
    """Override the models directory (used by `--models-dir`)."""
    global _models_dir_override
    _models_dir_override = Path(path).expanduser() if path else None


def set_sessions_dir(path: Path | None) -> None:
    global _sessions_dir_override
    _sessions_dir_override = Path(path).expanduser() if path else None


def set_qa_file_path(path: Path | None) -> None:
    global _qa_file_override
    _qa_file_override = Path(path).expanduser() if path else None


def models_dir() -> Path:
    if _models_dir_override is not None:
        return _models_dir_override
    xdg = os.environ.get("SPEAKLOOP_MODELS_DIR", "").strip()
    if xdg:
        return Path(xdg).expanduser()
    return _speakloop_home() / "models"


def sessions_dir() -> Path:
    if _sessions_dir_override is not None:
        return _sessions_dir_override
    raw = os.environ.get("SPEAKLOOP_SESSIONS_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.cwd() / "data" / "sessions"


def qa_file_path() -> Path:
    """The personal-override question file location (the `--qa-file` / env / home path).

    Unchanged semantics (004): an explicit `--qa-file` or SPEAKLOOP_QA_FILE wins,
    else the home override `~/.speakloop/qa.yaml`. This is the OVERRIDE location only;
    the in-repo default lives at `default_qa_file()` and the precedence chain that
    combines them is `resolve_qa_file()`.
    """
    if _qa_file_override is not None:
        return _qa_file_override
    raw = os.environ.get("SPEAKLOOP_QA_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _speakloop_home() / "qa.yaml"


def _explicit_qa_override() -> Path | None:
    """The explicit `--qa-file` / SPEAKLOOP_QA_FILE override, if one was supplied."""
    if _qa_file_override is not None:
        return _qa_file_override
    raw = os.environ.get("SPEAKLOOP_QA_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return None


def default_qa_file() -> Path:
    """The in-repo default question file: ``<cwd>/content/questions.yaml`` (004).

    CWD-relative, matching ``sessions_dir()``'s convention and the constitution's
    ``git clone`` + ``uv run`` model. Pure: does not check existence.
    """
    return Path.cwd() / "content" / "questions.yaml"


def resolve_qa_file() -> Path | None:
    """Active question file by precedence, or None if none is found/readable (004).

    Order (first match wins):
      1. an explicit ``--qa-file`` / SPEAKLOOP_QA_FILE override (used as given — a
         missing explicit path is the loader's error to surface, not silently
         skipped);
      2. the personal home override ``~/.speakloop/qa.yaml`` if it exists (opt-in by
         presence — wins over the in-repo default);
      3. the in-repo default ``content/questions.yaml`` if it exists;
      4. otherwise None, so the caller can emit an actionable message (FR-006).
    """
    explicit = _explicit_qa_override()
    if explicit is not None:
        return explicit
    home_override = _speakloop_home() / "qa.yaml"
    if home_override.exists():
        return home_override
    default = default_qa_file()
    if default.exists():
        return default
    return None


def tts_cache_dir() -> Path:
    raw = os.environ.get("SPEAKLOOP_TTS_CACHE_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _speakloop_home() / "cache" / "tts"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
