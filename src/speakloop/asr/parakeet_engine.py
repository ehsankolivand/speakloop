"""Parakeet-TDT-0.6b-v3 ASR wrapper.

This is the ONLY file in the repo allowed to `import parakeet_mlx`
(Constitution Principle V, audited by T109).

Real API (verified via `inspect.signature` against installed `parakeet_mlx==0.5.1`):

    parakeet_mlx.from_pretrained(hf_id_or_path, *, dtype=..., cache_dir=None) -> BaseParakeet
    BaseParakeet.transcribe(path: Path | str, *, dtype, decoding_config, ...) -> AlignedResult
    AlignedResult(text: str, sentences: list[AlignedSentence])
    AlignedSentence(text, tokens, start, end, duration, confidence)
    AlignedToken(id, text, start, duration, confidence, end)

Word-level timings come from flattening `result.sentences[i].tokens`; there
is no `result.words` attribute. The token's word string is `.text`, not `.word`.
"""

from __future__ import annotations

from pathlib import Path

import soundfile as sf

from speakloop.asr.interface import (
    ASREngineError,
    Transcript,
    TranscriptionContext,
    WordTiming,
)
from speakloop.installer.manifest import PARAKEET_TDT_06B_V3


class ParakeetEngine:
    """Parakeet TDT transcriber. RNN-T/TDT does not hallucinate on silence."""

    def __init__(self) -> None:
        self._model = None

    def ensure_loaded(self) -> None:
        """Eagerly load the model (idempotent) so engine selection can detect a
        load failure before attempt 1. Raises ASREngineError on failure."""
        self._load()

    def _load(self):  # pragma: no cover — engine-specific runtime
        if self._model is not None:
            return self._model
        try:
            import parakeet_mlx  # type: ignore
        except ImportError as e:
            raise ASREngineError(
                "parakeet_mlx is not installed. Install the Phase-B model bundle."
            ) from e
        model_path = PARAKEET_TDT_06B_V3.local_path
        if not model_path.exists():
            raise ASREngineError(
                f"Parakeet model not found at {model_path}. "
                "Run `speakloop practice` to consent and download it."
            )
        try:
            self._model = parakeet_mlx.from_pretrained(str(model_path))
        except Exception as e:
            raise ASREngineError(f"Parakeet load failed from {model_path}: {e}") from e
        return self._model

    def transcribe(
        self,
        wav_path: Path,
        *,
        context: TranscriptionContext | None = None,
    ) -> Transcript:
        # `context` (domain biasing / VAD toggle) is accepted for ASREngine
        # signature compatibility but ignored: Parakeet-TDT exposes no
        # contextual-biasing lever and does not hallucinate on silence
        # (research_asr.md), so neither initial_prompt nor VAD applies here.
        del context
        wav_path = Path(wav_path)
        # Read once to compute the audio duration for metric inputs; parakeet's
        # own transcribe() takes the path string and re-reads under the hood.
        try:
            info = sf.info(str(wav_path))
        except Exception as e:
            raise ASREngineError(f"Could not read WAV {wav_path}: {e}") from e
        duration = float(info.frames / info.samplerate) if info.samplerate else 0.0

        try:
            model = self._load()
            result = model.transcribe(str(wav_path))  # pragma: no cover
        except Exception as e:  # pragma: no cover
            raise ASREngineError(f"Parakeet transcription failed: {e}") from e

        words: list[WordTiming] = []
        for sentence in getattr(result, "sentences", []) or []:
            for token in getattr(sentence, "tokens", []) or []:
                words.append(
                    WordTiming(
                        word=str(getattr(token, "text", "")),
                        start_seconds=float(getattr(token, "start", 0.0)),
                        end_seconds=float(getattr(token, "end", 0.0)),
                    )
                )
        return Transcript(
            text=str(getattr(result, "text", "")).strip(),
            words=words,
            audio_duration_seconds=duration,
        )
