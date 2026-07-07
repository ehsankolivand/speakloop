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


# --- OpenRouter cloud mode (008) — PATHS ONLY ------------------------------
# These are pure path accessors (no reads), so the config leaf stays stdlib-only
# (see this module's CLAUDE.md "Never do"). The token file is the secret; the
# YAML holds the `model:` setting (read in llm/openrouter_config.py via pyyaml);
# the prompt file is the editable cloud system prompt.


def openrouter_token_path() -> Path:
    """The stored OpenRouter API token (``~/.speakloop/openrouter_token``)."""
    return _speakloop_home() / "openrouter_token"


def openrouter_config_path() -> Path:
    """The cloud settings YAML (``~/.speakloop/openrouter.yaml``; `model:` key)."""
    return _speakloop_home() / "openrouter.yaml"


def openrouter_prompt_path() -> Path:
    """The editable cloud system prompt (``~/.speakloop/openrouter_prompt.txt``)."""
    return _speakloop_home() / "openrouter_prompt.txt"


def openrouter_coach_prompt_path() -> Path:
    """The editable cloud coaching prompt (``~/.speakloop/openrouter_coach_prompt.txt``; 009).

    Separate from ``openrouter_prompt_path()`` (the strict grammar prompt): the
    coaching layer is a SECOND, additive cloud call that emits a free-form
    teaching section, so it gets its own independently tunable prompt file."""
    return _speakloop_home() / "openrouter_coach_prompt.txt"


# --- Interview Loop (010) — PATHS ONLY -------------------------------------
# The derived cross-session store (versioned JSON; SRS schedule + key-point cache
# + pattern aggregation) and the loop config (YAML; daily capacity + loop
# toggles). The store is an internal CACHE, rebuildable from session files via
# `speakloop rebuild`, so JSON is permitted (FR-040); the loop config is
# user-facing, so it is YAML. New seeded prompt files mirror the 008/009 cloud
# prompt pattern (one editable file per new cloud/analytic call).


def store_path() -> Path:
    """The derived cross-session store (``~/.speakloop/store.json``; 010).

    Internal cache only — fully rebuildable from ``data/sessions/*.md`` via
    `speakloop rebuild`, so it is never a source of truth."""
    return _speakloop_home() / "store.json"


def logs_dir() -> Path:
    """Directory for OPT-IN debug logs (``~/.speakloop/logs/``; 017). Only the explicit
    ``speakloop pronounce --debug`` flag writes here — a normal run creates nothing, preserving
    the "nothing in your home dir unless you put it there" guarantee. Caller mkdir-s on demand."""
    return _speakloop_home() / "logs"


def loop_config_path() -> Path:
    """The user-editable loop config YAML (``~/.speakloop/loop.yaml``; 010).

    Holds the daily due-queue capacity (default 5) and the warm-up/follow-up
    enable defaults. YAML because it is user-facing config (Constitution)."""
    return _speakloop_home() / "loop.yaml"


def openrouter_followups_prompt_path() -> Path:
    """Editable follow-up generation prompt (``~/.speakloop/openrouter_followups_prompt.txt``; 010)."""
    return _speakloop_home() / "openrouter_followups_prompt.txt"


def openrouter_keypoints_prompt_path() -> Path:
    """Editable key-point derivation prompt (``~/.speakloop/openrouter_keypoints_prompt.txt``; 010)."""
    return _speakloop_home() / "openrouter_keypoints_prompt.txt"


def openrouter_coverage_prompt_path() -> Path:
    """Editable coverage/content-error prompt (``~/.speakloop/openrouter_coverage_prompt.txt``; 010)."""
    return _speakloop_home() / "openrouter_coverage_prompt.txt"


def openrouter_triage_prompt_path() -> Path:
    """Editable mishearing-triage prompt (``~/.speakloop/openrouter_triage_prompt.txt``; 010)."""
    return _speakloop_home() / "openrouter_triage_prompt.txt"


def openrouter_drill_prompt_path() -> Path:
    """Editable warm-up drill prompt (``~/.speakloop/openrouter_drill_prompt.txt``; 010)."""
    return _speakloop_home() / "openrouter_drill_prompt.txt"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def seed_and_read(target: Path, default_asset: Path) -> tuple[str, Path]:
    """Seed `target` from `default_asset` on first use, then read it verbatim.

    The shared first-run prompt-seeding routine (IMP-035): the coverage/keypoints, follow-up,
    triage, warm-up-drill, and cloud grammar/coach loaders each copy their packaged default into
    the editable `~/.speakloop/` file the first time, then read the user's (possibly edited) file.
    Returns `(text, target)`.
    """
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(default_asset.read_text(encoding="utf-8"), encoding="utf-8")
    return target.read_text(encoding="utf-8"), target
