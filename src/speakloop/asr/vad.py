"""Voice-activity-detection pre-segmentation (Silero VAD via ONNX).

This is one of the engine-boundary files allowed to import a third-party engine
package — here `silero_vad` (Constitution Principle V; audited by
tests/unit/asr/test_engine_import_isolation.py). The import is function-local so
`speakloop --help` and non-practice commands never load it (Principle VIII).

Purpose: drop silence so the ASR never sees it (no hallucinated tokens in
thinking pauses — FR-006/SC-C), returning speech regions on the ORIGINAL audio
timeline so the Whisper engine can offset per-region word timings back and keep
the pause structure the fluency metrics depend on.

Thresholds trace to research §(b) / doc/research_asr_l2_accent.md §B.4. No SNR
gating / denoising ships here (out of scope this feature).

Dependency cap: `torchaudio<2.9` is pinned in pyproject — silero-vad's
`read_audio` uses torchaudio for audio I/O, and torchaudio>=2.11 routes decoding
through `torchcodec` (a separate, unbundled dep) which crashes the live session
on first VAD call; the <2.9 line keeps the in-tree FFmpeg/soundfile decode path.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

from speakloop.asr.interface import ASREngineError

SPEECH_THRESHOLD: float = 0.5
MIN_SPEECH_MS: int = 250
MIN_SILENCE_MS: int = 100
MERGE_GAP_MS: int = 300
SPEECH_PAD_MS: int = 30
SAMPLE_RATE_HZ: int = 16_000  # mono; required by Silero and Whisper


@dataclass(frozen=True)
class SpeechRegion:
    """A detected speech span on the original audio timeline (seconds)."""

    start_seconds: float
    end_seconds: float


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


def _merge(regions: list[SpeechRegion], gap_seconds: float) -> list[SpeechRegion]:
    """Merge adjacent regions separated by <= ``gap_seconds`` (research §b)."""
    if not regions:
        return []
    ordered = sorted(regions, key=lambda r: r.start_seconds)
    merged = [ordered[0]]
    for r in ordered[1:]:
        last = merged[-1]
        if r.start_seconds - last.end_seconds <= gap_seconds:
            merged[-1] = SpeechRegion(last.start_seconds, max(last.end_seconds, r.end_seconds))
        else:
            merged.append(r)
    return merged


def segment(wav_path: Path) -> list[SpeechRegion]:
    """Return merged, sorted, non-overlapping speech regions for the audio.

    Silero applies min-speech / min-silence / padding internally (configured from
    our tunables); we additionally merge regions within MERGE_GAP_MS. All-silence
    input returns ``[]`` (the caller then yields an empty Transcript).
    """
    wav_path = Path(wav_path)
    try:
        import silero_vad  # noqa: PLC0415 — function-local (Principle V/VIII)
    except ImportError as e:
        raise ASREngineError("silero-vad is not installed.") from e

    try:
        # silero_vad's read_audio routes through torchaudio, which (on the
        # <2.9 line we deliberately pin — see module docstring) emits
        # deprecation UserWarnings for sox_effects and the 2.9 backend
        # migration. We cannot upgrade past <2.9 (torchcodec crash), so
        # these are unactionable noise on every transcription — silence
        # them at the call site, scoped to torchaudio + silero_vad.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module=r"torchaudio\..*")
            warnings.filterwarnings("ignore", category=UserWarning, module=r"silero_vad\..*")
            audio = silero_vad.read_audio(str(wav_path), sampling_rate=SAMPLE_RATE_HZ)
            model = silero_vad.load_silero_vad(onnx=True)
            stamps = silero_vad.get_speech_timestamps(
                audio,
                model,
                threshold=SPEECH_THRESHOLD,
                sampling_rate=SAMPLE_RATE_HZ,
                min_speech_duration_ms=MIN_SPEECH_MS,
                min_silence_duration_ms=MIN_SILENCE_MS,
                speech_pad_ms=SPEECH_PAD_MS,
                return_seconds=True,
            )
    except Exception as e:  # pragma: no cover — runtime VAD failure
        raise ASREngineError(f"VAD segmentation failed for {wav_path}: {e}") from e

    regions = [SpeechRegion(float(s["start"]), float(s["end"])) for s in stamps]
    return _merge(regions, gap_seconds=MERGE_GAP_MS / 1000.0)
