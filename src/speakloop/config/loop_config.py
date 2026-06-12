"""Daily-loop user config (010-interview-loop, P2).

A small user-editable YAML file (``~/.speakloop/loop.yaml``) holding the daily
due-queue capacity and the warm-up / follow-up enable defaults. YAML because it is
user-facing configuration (Constitution / FR-040). Not auto-created — absent or
malformed file falls back to the built-in defaults (mirrors the qa.yaml opt-in
model: no file is written for the user).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from speakloop.config import paths

DEFAULT_DAILY_CAPACITY = 5

# 011: default analysis engine + Claude Code model tiers. All additive optional.
DEFAULT_ENGINE = "local"
VALID_ENGINES = ("local", "openrouter", "claude")
DEFAULT_CLAUDE_FAST_MODEL = "haiku"
DEFAULT_CLAUDE_STRONG_MODEL = "sonnet"
# Per-call hard timeout for the Claude Code engine. Raised from the engine's 90s
# baseline because a strong-tier model (esp. Opus with extended thinking) running the
# full grammar prompt over 3 attempts can take well over 90s.
DEFAULT_CLAUDE_TIMEOUT_SECONDS = 240

# 012 (additive optional): ideal-answer autoplay toggle + analysis concurrency cap.
DEFAULT_AUTOPLAY_IDEAL_ANSWER = True
DEFAULT_ANALYSIS_CONCURRENCY = 3

# 016 (additive optional): read-aloud pronunciation-drill default + safety threshold.
DEFAULT_PRONUNCIATION_DRILLS = "auto"  # auto (offer when safe) | on | off
VALID_PRONUNCIATION_DRILLS = ("auto", "on", "off")
# Free RAM (MB) required before drills are offered on a cloud engine: the pronunciation
# model peaks ~3 GB; 4500 MB leaves headroom (conservative — borderline machines skip).
DEFAULT_PRONUNCIATION_MIN_FREE_MB = 4500


@dataclass(frozen=True)
class LoopConfig:
    daily_capacity: int = DEFAULT_DAILY_CAPACITY
    warmup_enabled: bool = True
    followups_enabled: bool = True
    # 011 (additive optional): default engine + Claude Code model tiers + timeout.
    engine: str = DEFAULT_ENGINE
    claude_fast_model: str = DEFAULT_CLAUDE_FAST_MODEL
    claude_strong_model: str = DEFAULT_CLAUDE_STRONG_MODEL
    claude_timeout_seconds: int = DEFAULT_CLAUDE_TIMEOUT_SECONDS
    # 012 (additive optional): never-forced-to-relisten toggle + concurrent-analysis cap.
    autoplay_ideal_answer: bool = DEFAULT_AUTOPLAY_IDEAL_ANSWER
    analysis_concurrency: int = DEFAULT_ANALYSIS_CONCURRENCY
    # 016 (additive optional): read-aloud pronunciation-drill default + free-RAM threshold.
    pronunciation_drills: str = DEFAULT_PRONUNCIATION_DRILLS
    pronunciation_min_free_mb: int = DEFAULT_PRONUNCIATION_MIN_FREE_MB


def _model(data: dict, key: str, default: str) -> str:
    val = data.get(key, default)
    return val if isinstance(val, str) and val.strip() else default


def load() -> LoopConfig:
    """Return the loop config, or built-in defaults when the file is absent/invalid."""
    path = paths.loop_config_path()
    if not path.exists():
        return LoopConfig()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return LoopConfig()
    if not isinstance(data, dict):
        return LoopConfig()
    cap = data.get("daily_capacity", DEFAULT_DAILY_CAPACITY)
    try:
        cap = max(1, int(cap))
    except (TypeError, ValueError):
        cap = DEFAULT_DAILY_CAPACITY
    engine = data.get("engine", DEFAULT_ENGINE)
    if not isinstance(engine, str) or engine not in VALID_ENGINES:
        engine = DEFAULT_ENGINE
    try:
        timeout = max(1, int(data.get("claude_timeout_seconds", DEFAULT_CLAUDE_TIMEOUT_SECONDS)))
    except (TypeError, ValueError):
        timeout = DEFAULT_CLAUDE_TIMEOUT_SECONDS
    try:
        concurrency = max(1, int(data.get("analysis_concurrency", DEFAULT_ANALYSIS_CONCURRENCY)))
    except (TypeError, ValueError):
        concurrency = DEFAULT_ANALYSIS_CONCURRENCY
    autoplay = data.get("autoplay_ideal_answer", DEFAULT_AUTOPLAY_IDEAL_ANSWER)
    if not isinstance(autoplay, bool):
        autoplay = DEFAULT_AUTOPLAY_IDEAL_ANSWER
    drills = data.get("pronunciation_drills", DEFAULT_PRONUNCIATION_DRILLS)
    if not isinstance(drills, str) or drills not in VALID_PRONUNCIATION_DRILLS:
        drills = DEFAULT_PRONUNCIATION_DRILLS
    try:
        min_free_mb = max(0, int(data.get("pronunciation_min_free_mb", DEFAULT_PRONUNCIATION_MIN_FREE_MB)))
    except (TypeError, ValueError):
        min_free_mb = DEFAULT_PRONUNCIATION_MIN_FREE_MB
    return LoopConfig(
        daily_capacity=cap,
        warmup_enabled=bool(data.get("warmup_enabled", True)),
        followups_enabled=bool(data.get("followups_enabled", True)),
        engine=engine,
        claude_fast_model=_model(data, "claude_fast_model", DEFAULT_CLAUDE_FAST_MODEL),
        claude_strong_model=_model(data, "claude_strong_model", DEFAULT_CLAUDE_STRONG_MODEL),
        claude_timeout_seconds=timeout,
        autoplay_ideal_answer=autoplay,
        analysis_concurrency=concurrency,
        pronunciation_drills=drills,
        pronunciation_min_free_mb=min_free_mb,
    )


def save_engine(engine: str) -> Path:
    """Persist the default feedback engine to ``loop.yaml`` (015). Returns the path written.

    The ONLY writer of ``loop.yaml`` — an explicit, user-initiated action (``speakloop
    setup``); no normal run auto-creates or edits the file, preserving the "nothing is
    created in your home directory unless you put it there" guarantee. Validates against
    ``VALID_ENGINES``, then read-modify-writes so any other keys the user set are kept.

    Refuses to overwrite a file it can't safely round-trip: if an existing, non-empty
    ``loop.yaml`` does not parse as a YAML mapping (a hand-edit typo, or a top-level
    list/scalar) this raises ``ValueError`` rather than clobbering the user's other settings
    with a fresh one-key file. An empty or comments-only file is treated as no keys. pyyaml
    does not preserve comments, so a hand-commented file loses comments on a valid rewrite.
    """
    if engine not in VALID_ENGINES:
        raise ValueError(f"engine must be one of {', '.join(VALID_ENGINES)} (got {engine!r}).")
    path = paths.loop_config_path()
    data: dict = {}
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ValueError(
                f"Refusing to overwrite {path}: it is not valid YAML ({e.__class__.__name__}). "
                "Fix the file by hand (or delete it), then re-run."
            ) from e
        if loaded is None:
            data = {}  # empty or comments-only — safe to start fresh
        elif isinstance(loaded, dict):
            data = loaded
        else:
            raise ValueError(
                f"Refusing to overwrite {path}: its top level is a {type(loaded).__name__}, "
                "not a key/value mapping. Fix the file by hand (or delete it), then re-run."
            )
    data["engine"] = engine
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
