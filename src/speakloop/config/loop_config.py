"""Daily-loop user config (010-interview-loop, P2).

A small user-editable YAML file (``~/.speakloop/loop.yaml``) holding the daily
due-queue capacity and the warm-up / follow-up enable defaults. YAML because it is
user-facing configuration (Constitution / FR-040). Not auto-created — absent or
malformed file falls back to the built-in defaults (mirrors the qa.yaml opt-in
model: no file is written for the user).
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from speakloop.config import paths

DEFAULT_DAILY_CAPACITY = 5

# 011: default analysis engine + Claude Code model tiers. All additive optional.
DEFAULT_ENGINE = "local"
VALID_ENGINES = ("local", "openrouter", "claude")
DEFAULT_CLAUDE_FAST_MODEL = "haiku"
DEFAULT_CLAUDE_STRONG_MODEL = "sonnet"


@dataclass(frozen=True)
class LoopConfig:
    daily_capacity: int = DEFAULT_DAILY_CAPACITY
    warmup_enabled: bool = True
    followups_enabled: bool = True
    # 011 (additive optional): default engine + Claude Code model tiers.
    engine: str = DEFAULT_ENGINE
    claude_fast_model: str = DEFAULT_CLAUDE_FAST_MODEL
    claude_strong_model: str = DEFAULT_CLAUDE_STRONG_MODEL


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
    return LoopConfig(
        daily_capacity=cap,
        warmup_enabled=bool(data.get("warmup_enabled", True)),
        followups_enabled=bool(data.get("followups_enabled", True)),
        engine=engine,
        claude_fast_model=_model(data, "claude_fast_model", DEFAULT_CLAUDE_FAST_MODEL),
        claude_strong_model=_model(data, "claude_strong_model", DEFAULT_CLAUDE_STRONG_MODEL),
    )
