"""Contract: voice-activity-detection pre-segmentation (asr/vad.py).

This is the ONLY module (besides whisper_mlx_engine.py / parakeet_engine.py)
allowed to import a third-party engine package — here `silero_vad` and
`onnxruntime` (Constitution Principle V). Thresholds trace to research §(b) and
`doc/research_asr_l2_accent.md` §B.4.

Purpose: drop silence so the ASR never sees it (no hallucinated tokens in
thinking pauses — FR-006, SC-C), while returning regions on the ORIGINAL timeline
so the Whisper engine can offset per-region word timings back and preserve the
pause structure the fluency metrics depend on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Named tunables (research §(b)). No SNR gating ships in this feature; denoising
# is out of scope (revisit only if repro tests show audio quality is the
# bottleneck — brief §B.4/§B.5).
SPEECH_THRESHOLD: float = 0.5
MIN_SPEECH_MS: int = 250
MIN_SILENCE_MS: int = 100
MERGE_GAP_MS: int = 300
SPEECH_PAD_MS: int = 30
SAMPLE_RATE_HZ: int = 16_000  # mono; required by Silero and Whisper


@dataclass(frozen=True)
class SpeechRegion:
    """A detected speech span on the original audio timeline."""

    start_seconds: float
    end_seconds: float


def segment(wav_path: Path) -> list[SpeechRegion]:
    """Return merged, sorted, non-overlapping speech regions for the audio.

    Contract:
      - input is read as 16 kHz mono (resampled if needed);
      - regions shorter than MIN_SPEECH_MS are dropped;
      - adjacent regions separated by <= MERGE_GAP_MS are merged;
      - each kept region is padded by SPEECH_PAD_MS on both sides (clamped to
        [0, duration]);
      - all-silence input returns [] (caller yields an empty Transcript);
      - regions are on the ORIGINAL timeline (start/end in original seconds).

    Raises ASREngineError on unreadable audio.
    """
    ...


def vad_settings() -> dict:
    """The tunables that ran, for the frontmatter `asr.vad` provenance block."""
    return {
        "engine": "silero",
        "speech_threshold": SPEECH_THRESHOLD,
        "min_speech_ms": MIN_SPEECH_MS,
        "min_silence_ms": MIN_SILENCE_MS,
        "merge_gap_ms": MERGE_GAP_MS,
        "speech_pad_ms": SPEECH_PAD_MS,
    }
