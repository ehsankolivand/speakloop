"""ASR engine selection + graceful fallback (FR-002/FR-009/SC-F).

Resolves which engine runs: the default Whisper, an explicit `--asr-engine`
choice, or — if the requested engine cannot load — an automatic fallback to
Parakeet with one English reason line. The load is **probed eagerly** (via
``ensure_loaded``) so a missing model or OOM surfaces before attempt 1.

Principle V: this module imports the two wrapper CLASSES (both inside ``asr/``)
but no third-party engine package itself — the engine-specific imports stay in
``whisper_mlx_engine`` / ``parakeet_engine``.
"""

from __future__ import annotations

from dataclasses import dataclass

from speakloop.asr.interface import ASREngine, ASREngineError
from speakloop.asr.parakeet_engine import ParakeetEngine
from speakloop.asr.whisper_mlx_engine import WhisperMLXEngine
from speakloop.installer.manifest import PARAKEET_TDT_06B_V3, WHISPER_LARGE_V3_TURBO

WHISPER = "whisper"
PARAKEET = "parakeet"


@dataclass(frozen=True)
class EngineSelection:
    """The engine that actually runs, plus provenance for the report."""

    engine: ASREngine
    engine_name: str
    model_id: str
    fell_back: bool
    fallback_reason: str | None = None


def _build_parakeet() -> EngineSelection:
    engine = ParakeetEngine()
    engine.ensure_loaded()
    return EngineSelection(
        engine=engine,
        engine_name=PARAKEET,
        model_id=PARAKEET_TDT_06B_V3.hf_repo_id,
        fell_back=False,
    )


def build_engine(name: str | None = None) -> EngineSelection:
    """Construct + eagerly load the requested engine (default: whisper).

    On load failure of the requested engine, fall back to Parakeet with an
    English ``fallback_reason``. An explicit ``parakeet`` is honored with no
    fallback. The returned engine is resident and reused across attempts,
    sessions, and replays with no reload (research §c).
    """
    requested = (name or WHISPER).lower()

    if requested == PARAKEET:
        return _build_parakeet()

    # Default / explicit Whisper: probe the load eagerly.
    engine = WhisperMLXEngine()
    try:
        engine.ensure_loaded()
    except ASREngineError as e:
        fallback = _build_parakeet()
        return EngineSelection(
            engine=fallback.engine,
            engine_name=PARAKEET,
            model_id=fallback.model_id,
            fell_back=True,
            fallback_reason=str(e),
        )
    return EngineSelection(
        engine=engine,
        engine_name=WHISPER,
        model_id=WHISPER_LARGE_V3_TURBO.hf_repo_id,
        fell_back=False,
    )
