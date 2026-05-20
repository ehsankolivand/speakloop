"""Whisper-large-v3-turbo ASR wrapper (mlx-whisper) — the DEFAULT engine.

This is the ONLY file in the repo allowed to `import mlx_whisper` (Constitution
Principle V; audited by tests/unit/asr/test_engine_import_isolation.py). All
`mlx_whisper` / `mlx` imports are **function-local** so `speakloop --help` and
non-practice commands never load the engine (Principle VIII).

Real API (verified against installed mlx-whisper==0.4.3):
    mlx_whisper.transcribe(audio, *, path_or_hf_repo, initial_prompt,
        condition_on_previous_text, word_timestamps, language, ...) -> dict
    result["text"]: str
    result["segments"][i]["words"][j] = {"word", "start", "end", "probability"}
The model is cached process-wide by `ModelHolder` keyed on path, so repeated
transcriptions reuse one resident copy (research §c).

VAD pre-segmentation is added in US2 (`asr/vad.py`); US1 transcribes the whole
clip with `initial_prompt` biasing.
"""

from __future__ import annotations

import logging
import zlib
from pathlib import Path

import soundfile as sf

from speakloop.asr.interface import ASREngineError, Transcript, TranscriptionContext, WordTiming
from speakloop.installer.manifest import WHISPER_LARGE_V3_TURBO

logger = logging.getLogger(__name__)

# Documented Whisper anti-hallucination decoding flags (OpenAI whisper README;
# discussions referenced in doc/research_asr_l2_accent.md §B.4). Passing them
# explicitly enables the built-in temperature-fallback: when a decode fails the
# compression-ratio or logprob check, Whisper retries at the next-higher
# temperature, which breaks the low-confidence repetition loop ("Come Come
# Come…" observed on a 15.8 s attempt). Values mirror mlx_whisper's own defaults.
_DECODE_GUARDS = {
    "temperature": (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    "compression_ratio_threshold": 2.4,
    "logprob_threshold": -1.0,
    "no_speech_threshold": 0.6,
}


def _is_degenerate(text: str) -> bool:
    """True if `text` looks like a Whisper repetition loop.

    Uses Whisper's own degeneracy signal: a gzip compression ratio above
    `compression_ratio_threshold` (2.4) means the text is far more repetitive
    than natural speech (e.g. one token repeated hundreds of times). This is a
    post-hoc safety net for the rare case the temperature fallback still returns
    a degenerate decode."""
    t = text.strip()
    if len(t) < 16:
        return False
    raw = t.encode("utf-8")
    compressed = zlib.compress(raw)
    ratio = len(raw) / len(compressed) if compressed else 0.0
    return ratio > _DECODE_GUARDS["compression_ratio_threshold"]


class WhisperMLXEngine:
    """Whisper transcriber with `initial_prompt` contextual biasing."""

    def __init__(self) -> None:
        self._loaded = False

    def _load(self) -> None:  # pragma: no cover — exercised only with real weights
        """Load the model once into the process-wide cache mlx_whisper uses, so a
        load failure (missing files, OOM) surfaces here and there is exactly one
        resident copy. Idempotent."""
        if self._loaded:
            return
        try:
            import mlx.core as mx  # noqa: PLC0415 — function-local (Principle V/VIII)
            from mlx_whisper.transcribe import ModelHolder  # noqa: PLC0415
        except ImportError as e:
            raise ASREngineError(
                "mlx-whisper is not installed. Install the Phase-B model bundle."
            ) from e
        model_path = WHISPER_LARGE_V3_TURBO.local_path
        if not model_path.exists():
            raise ASREngineError(
                f"Whisper model not found at {model_path}. "
                "Run `speakloop practice` to consent and download it."
            )
        try:
            # dtype matches mlx_whisper.transcribe's default (fp16) so transcribe's
            # own ModelHolder.get_model() is a cache hit — no second load.
            ModelHolder.get_model(str(model_path), mx.float16)
        except Exception as e:
            raise ASREngineError(f"Whisper load failed from {model_path}: {e}") from e
        self._loaded = True

    def ensure_loaded(self) -> None:
        self._load()

    def _load_audio(self, wav_path: Path):  # pragma: no cover — needs ffmpeg/audio
        """Load the audio as a 16 kHz mono float32 array (for VAD-region slicing)."""
        import mlx_whisper  # noqa: PLC0415 — function-local (Principle V/VIII)

        return mlx_whisper.audio.load_audio(str(wav_path))

    def transcribe(
        self,
        wav_path: Path,
        *,
        context: TranscriptionContext | None = None,
    ) -> Transcript:
        wav_path = Path(wav_path)
        self._load()
        initial_prompt = context.initial_prompt if context is not None else None
        use_vad = context.use_vad if context is not None else True

        try:
            import mlx_whisper  # noqa: PLC0415 — function-local (Principle V/VIII)

            if use_vad:
                return self._transcribe_with_vad(mlx_whisper, wav_path, initial_prompt)

            # Whole-clip path: derive duration from the file header.
            try:
                info = sf.info(str(wav_path))
            except Exception as e:
                raise ASREngineError(f"Could not read WAV {wav_path}: {e}") from e
            duration = float(info.frames / info.samplerate) if info.samplerate else 0.0
            result = mlx_whisper.transcribe(  # pragma: no cover — needs weights
                str(wav_path),
                path_or_hf_repo=str(WHISPER_LARGE_V3_TURBO.local_path),
                initial_prompt=initial_prompt,
                condition_on_previous_text=False,  # short clips: avoid context drift
                language="en",  # forced: don't mis-detect accented English
                word_timestamps=True,
                **_DECODE_GUARDS,
            )
        except ASREngineError:
            raise
        except Exception as e:
            raise ASREngineError(f"Whisper transcription failed: {e}") from e

        transcript = _result_to_transcript(result, duration)
        if _is_degenerate(transcript.text):
            logger.warning(
                "Whisper produced a degenerate repetition loop "
                "(compression ratio > %.1f); dropping the transcript.",
                _DECODE_GUARDS["compression_ratio_threshold"],
            )
            return Transcript(text="", words=[], audio_duration_seconds=duration)
        return transcript

    def _transcribe_with_vad(self, mlx_whisper, wav_path, initial_prompt):
        """Drop silence via VAD, transcribe each speech region, and stitch word
        timings back onto the original timeline (research §b; FR-005/FR-006).

        Duration is derived from the loaded 16 kHz audio so the silent regions
        still count toward total time (preserving pause/rate metrics)."""
        from speakloop.asr import vad  # noqa: PLC0415

        audio = self._load_audio(wav_path)
        sr = vad.SAMPLE_RATE_HZ
        duration = (len(audio) / sr) if sr else 0.0

        regions = vad.segment(wav_path)
        if not regions:
            # Pure silence (or VAD removed everything) → empty transcript.
            return Transcript(text="", words=[], audio_duration_seconds=duration)
        texts: list[str] = []
        words: list[WordTiming] = []
        for region in regions:
            start = max(0, int(region.start_seconds * sr))
            end = min(len(audio), int(region.end_seconds * sr))
            if end <= start:
                continue
            clip = audio[start:end]
            result = mlx_whisper.transcribe(
                clip,
                path_or_hf_repo=str(WHISPER_LARGE_V3_TURBO.local_path),
                initial_prompt=initial_prompt,
                condition_on_previous_text=False,
                language="en",
                word_timestamps=True,
                **_DECODE_GUARDS,
            )
            piece = _result_to_transcript(result, 0.0)
            if _is_degenerate(piece.text):
                logger.warning(
                    "Whisper produced a degenerate repetition loop in the "
                    "speech region [%.2fs, %.2fs] (compression ratio > %.1f); "
                    "dropping that region.",
                    region.start_seconds,
                    region.end_seconds,
                    _DECODE_GUARDS["compression_ratio_threshold"],
                )
                continue
            if piece.text:
                texts.append(piece.text)
            # Offset each region's word timings back onto the original timeline so
            # the inter-region silences survive as gaps (pause metrics stay correct).
            for w in piece.words:
                words.append(
                    WordTiming(
                        word=w.word,
                        start_seconds=w.start_seconds + region.start_seconds,
                        end_seconds=w.end_seconds + region.start_seconds,
                    )
                )
        return Transcript(
            text=" ".join(texts).strip(),
            words=words,
            audio_duration_seconds=duration,
        )


def _result_to_transcript(result: dict, duration: float) -> Transcript:
    """Map an mlx_whisper result dict to a Transcript (timeline as returned)."""
    words: list[WordTiming] = []
    for segment in result.get("segments", []) or []:
        for w in segment.get("words", []) or []:
            words.append(
                WordTiming(
                    word=str(w.get("word", "")).strip(),
                    start_seconds=float(w.get("start", 0.0)),
                    end_seconds=float(w.get("end", 0.0)),
                )
            )
    return Transcript(
        text=str(result.get("text", "")).strip(),
        words=words,
        audio_duration_seconds=duration,
    )
