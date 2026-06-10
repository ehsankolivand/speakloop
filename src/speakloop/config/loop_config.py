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


@dataclass(frozen=True)
class LoopConfig:
    daily_capacity: int = DEFAULT_DAILY_CAPACITY
    warmup_enabled: bool = True
    followups_enabled: bool = True


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
    return LoopConfig(
        daily_capacity=cap,
        warmup_enabled=bool(data.get("warmup_enabled", True)),
        followups_enabled=bool(data.get("followups_enabled", True)),
    )
