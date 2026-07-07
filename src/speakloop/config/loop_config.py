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
# Optional reasoning-effort level per Claude Code tier. Unset by default (None) → the engine
# emits no `--effort` flag, so behaviour and older CLI builds are unaffected; opt in via
# loop.yaml. A value outside the known set is treated as unset (parsed in load()).
DEFAULT_CLAUDE_FAST_EFFORT: str | None = None
DEFAULT_CLAUDE_STRONG_EFFORT: str | None = None
VALID_CLAUDE_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
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

# 017 (additive optional): hear → say → see → retry trainer knobs.
# Play the target with the local TTS before each drill so the learner hears it first.
DEFAULT_PRONUNCIATION_TTS_PLAYBACK = True
# Bounded per-item retries when a sound is flagged (0 = 016 one-shot behaviour). Clamped 0..3.
DEFAULT_PRONUNCIATION_RETRIES = 1
MAX_PRONUNCIATION_RETRIES = 3
# Kokoro playback-speed multiplier for the trainer (< 1.0 = slower → easier to imitate). The
# learner reported the default 1.0 read too fast to shadow; 0.85 is a clearer coaching cadence.
# Clamped to a sane band so a hand-edit can't make playback unusable. The focused per-sound
# teaching beat plays even slower (a fixed factor below this).
DEFAULT_PRONUNCIATION_TTS_SPEED = 0.85
MIN_PRONUNCIATION_TTS_SPEED = 0.5
MAX_PRONUNCIATION_TTS_SPEED = 1.5


@dataclass(frozen=True)
class LoopConfig:
    daily_capacity: int = DEFAULT_DAILY_CAPACITY
    warmup_enabled: bool = True
    followups_enabled: bool = True
    # 011 (additive optional): default engine + Claude Code model tiers + timeout.
    engine: str = DEFAULT_ENGINE
    claude_fast_model: str = DEFAULT_CLAUDE_FAST_MODEL
    claude_strong_model: str = DEFAULT_CLAUDE_STRONG_MODEL
    claude_fast_effort: str | None = DEFAULT_CLAUDE_FAST_EFFORT
    claude_strong_effort: str | None = DEFAULT_CLAUDE_STRONG_EFFORT
    claude_timeout_seconds: int = DEFAULT_CLAUDE_TIMEOUT_SECONDS
    # 012 (additive optional): never-forced-to-relisten toggle + concurrent-analysis cap.
    autoplay_ideal_answer: bool = DEFAULT_AUTOPLAY_IDEAL_ANSWER
    analysis_concurrency: int = DEFAULT_ANALYSIS_CONCURRENCY
    # 016 (additive optional): read-aloud pronunciation-drill default + free-RAM threshold.
    pronunciation_drills: str = DEFAULT_PRONUNCIATION_DRILLS
    pronunciation_min_free_mb: int = DEFAULT_PRONUNCIATION_MIN_FREE_MB
    # 017 (additive optional): hear-first TTS playback toggle + bounded per-item retries
    # + trainer playback speed.
    pronunciation_tts_playback: bool = DEFAULT_PRONUNCIATION_TTS_PLAYBACK
    pronunciation_retries: int = DEFAULT_PRONUNCIATION_RETRIES
    pronunciation_tts_speed: float = DEFAULT_PRONUNCIATION_TTS_SPEED


def _model(data: dict, key: str, default: str) -> str:
    val = data.get(key, default)
    return val if isinstance(val, str) and val.strip() else default


def _effort(data: dict, key: str) -> str | None:
    """A Claude Code effort level, normalized to lowercase; unset/unknown → None (no flag)."""
    val = data.get(key)
    if isinstance(val, str) and val.strip().lower() in VALID_CLAUDE_EFFORT_LEVELS:
        return val.strip().lower()
    return None


def _int(data: dict, key: str, default: int, *, floor: int | None = None, ceil: int | None = None) -> int:
    """Read an int scalar; a non-numeric value → ``default``. Clamp to ``[floor, ceil]``."""
    try:
        value = int(data.get(key, default))
    except (TypeError, ValueError):
        return default
    if floor is not None:
        value = max(floor, value)
    if ceil is not None:
        value = min(ceil, value)
    return value


def _float(data: dict, key: str, default: float, *, floor: float | None = None, ceil: float | None = None) -> float:
    """Read a float scalar; a non-numeric value → ``default``. Clamp to ``[floor, ceil]``."""
    try:
        value = float(data.get(key, default))
    except (TypeError, ValueError):
        return default
    if floor is not None:
        value = max(floor, value)
    if ceil is not None:
        value = min(ceil, value)
    return value


def _bool(data: dict, key: str, default: bool) -> bool:
    """Read a bool scalar; a non-bool value → ``default`` (isinstance, so ``0``/``"yes"`` do
    NOT silently coerce — distinct from the `bool()`-cast `warmup_enabled`/`followups_enabled`)."""
    value = data.get(key, default)
    return value if isinstance(value, bool) else default


def _choice(data: dict, key: str, default: str, valid: tuple[str, ...]) -> str:
    """Read a string scalar restricted to ``valid``; anything else → ``default``."""
    value = data.get(key, default)
    return value if isinstance(value, str) and value in valid else default


def teach_speed(drill_speed: float) -> float:
    """The slower playback speed for the focused per-sound TEACHING beat (017 P2), derived
    from the drill playback speed so it is always a step slower (clamped to the sane floor).
    Kept here (a leaf module both ``cli`` and ``sessions`` import) so both callers agree."""
    return round(max(MIN_PRONUNCIATION_TTS_SPEED, float(drill_speed) * 0.8), 2)


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
    return LoopConfig(
        daily_capacity=_int(data, "daily_capacity", DEFAULT_DAILY_CAPACITY, floor=1),
        warmup_enabled=bool(data.get("warmup_enabled", True)),
        followups_enabled=bool(data.get("followups_enabled", True)),
        engine=_choice(data, "engine", DEFAULT_ENGINE, VALID_ENGINES),
        claude_fast_model=_model(data, "claude_fast_model", DEFAULT_CLAUDE_FAST_MODEL),
        claude_strong_model=_model(data, "claude_strong_model", DEFAULT_CLAUDE_STRONG_MODEL),
        claude_fast_effort=_effort(data, "claude_fast_effort"),
        claude_strong_effort=_effort(data, "claude_strong_effort"),
        claude_timeout_seconds=_int(
            data, "claude_timeout_seconds", DEFAULT_CLAUDE_TIMEOUT_SECONDS, floor=1
        ),
        autoplay_ideal_answer=_bool(data, "autoplay_ideal_answer", DEFAULT_AUTOPLAY_IDEAL_ANSWER),
        analysis_concurrency=_int(
            data, "analysis_concurrency", DEFAULT_ANALYSIS_CONCURRENCY, floor=1
        ),
        pronunciation_drills=_choice(
            data, "pronunciation_drills", DEFAULT_PRONUNCIATION_DRILLS, VALID_PRONUNCIATION_DRILLS
        ),
        pronunciation_min_free_mb=_int(
            data, "pronunciation_min_free_mb", DEFAULT_PRONUNCIATION_MIN_FREE_MB, floor=0
        ),
        pronunciation_tts_playback=_bool(
            data, "pronunciation_tts_playback", DEFAULT_PRONUNCIATION_TTS_PLAYBACK
        ),
        pronunciation_retries=_int(
            data, "pronunciation_retries", DEFAULT_PRONUNCIATION_RETRIES,
            floor=0, ceil=MAX_PRONUNCIATION_RETRIES,
        ),
        pronunciation_tts_speed=_float(
            data, "pronunciation_tts_speed", DEFAULT_PRONUNCIATION_TTS_SPEED,
            floor=MIN_PRONUNCIATION_TTS_SPEED, ceil=MAX_PRONUNCIATION_TTS_SPEED,
        ),
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
