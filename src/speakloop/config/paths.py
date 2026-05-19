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
    if _qa_file_override is not None:
        return _qa_file_override
    raw = os.environ.get("SPEAKLOOP_QA_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _speakloop_home() / "qa.yaml"


def tts_cache_dir() -> Path:
    raw = os.environ.get("SPEAKLOOP_TTS_CACHE_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _speakloop_home() / "cache" / "tts"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
