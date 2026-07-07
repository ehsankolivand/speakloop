"""wav2vec2 CTC phoneme scorer — the ONLY file importing ``torch`` / ``transformers``.

Both imports are function-local in ``_load()`` (Principle V; root CLAUDE.md O1), so
``speakloop --help`` and the CLI import never load them — guarded by
``tests/integration/test_help_without_models.py`` and
``tests/unit/asr/test_engine_import_isolation.py``.

Model: ``facebook/wav2vec2-lv-60-espeak-cv-ft`` (Apache-2.0), run on CPU. Pipeline:
audio → logits → log-softmax ``[T, vocab]`` → pure-numpy CTC forced alignment + GOP
(``gop.py``) → calibrated ``PhoneFlag``s. ``score`` NEVER raises into the session.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from speakloop.installer import manifest
from speakloop.pronunciation import gop
from speakloop.pronunciation.interface import (
    DrillResult,
    PhoneFlag,
    PronunciationError,
    PronunciationScorer,
)

_SAMPLE_RATE = 16_000
# Tunable scoring thresholds, in nats of log-posterior. CALIBRATED against the live
# harness (every bundled drill TTS-rendered → scored): a clean rendering of the target
# phone scores GOP ≳ -0.9 with the competitor LOSING (margin < 0), while a deliberate
# substitution on the target scores GOP ≲ -2.4 with the competitor winning by margin
# ≳ +2.0. A phone is flagged when it is pronounced poorly (low GOP) OR a competitor
# CLEARLY beats it. The GOP bound alone separates clean from substituted; the competitor
# margin is a corroborating signal set high (1.5, between the clean ≤0 and error ≥+2.0
# clusters) so a borderline-but-acceptable read is not over-flagged on margin alone
# (the 0.5 first-pass value over-flagged accented-but-fine sounds — e.g. /w/). The
# diagnosis ("heard as …") is suggested only with a clear competitor margin.
_GOP_FLAG_THRESHOLD = -2.0
_COMPETITOR_FLAG_MARGIN = 1.5
_DIAGNOSIS_MARGIN = 1.0
_MIN_SPEECH_RMS = 1.5e-3
_MIN_SPEECH_SECONDS = 0.2


def build_scorer() -> PronunciationScorer:
    """Construct the wav2vec2-backed scorer (model loads lazily on first ``score``)."""
    return Wav2Vec2Scorer()


class Wav2Vec2Scorer:
    """Lazy, CPU-only wav2vec2 phoneme scorer implementing ``PronunciationScorer``."""

    def __init__(self) -> None:
        self._feature_extractor = None
        self._model = None
        self._sym2id: dict[str, int] = {}
        self._blank_id = 0

    # -- lifecycle ----------------------------------------------------------------
    def _load(self) -> None:
        if self._model is not None:
            return
        model_path = manifest.WAV2VEC2_PRONUNCIATION.local_path
        if not model_path.exists():
            raise PronunciationError(
                f"Pronunciation model not found at {model_path}. Opt into drills to download it."
            )
        try:
            import torch  # noqa: F401  (function-local — keeps --help model-free)
            from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC
        except Exception as e:  # noqa: BLE001
            raise PronunciationError(f"transformers/torch unavailable: {e}") from e
        try:
            # Load ONLY the audio feature extractor + the CTC model + the vocab map. We
            # deliberately do NOT build a Wav2Vec2Processor / Wav2Vec2PhonemeCTCTokenizer:
            # that tokenizer's __init__ eagerly spins up the espeak *phonemizer* (text →
            # phoneme) backend, which the scorer NEVER uses (it ships bundled canonical
            # phonemes per drill) and which makes the whole model load crash with
            # "espeak not installed on your system" when the system espeak library is
            # absent or in a fragile state — surfacing to the learner as every drill
            # "could not score this one". Reading vocab.json directly keeps the scorer
            # truly offline (Constitution II) and the load deterministic across runs.
            self._feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(str(model_path))
            self._sym2id = self._read_vocab(model_path)
            self._blank_id = int(self._sym2id.get("<pad>", 0))
            model = Wav2Vec2ForCTC.from_pretrained(str(model_path))
            model.eval()
            model.to("cpu")
            self._model = model
        except PronunciationError:
            raise
        except Exception as e:  # noqa: BLE001
            raise PronunciationError(f"could not load pronunciation model: {e}") from e

    @staticmethod
    def _read_vocab(model_path: Path) -> dict[str, int]:
        """Read the model's symbol → id map from the bundled ``vocab.json`` (no tokenizer →
        no phonemizer/espeak). Mirrors the live harness's direct vocab read."""
        import json

        vocab_file = model_path / "vocab.json"
        if not vocab_file.exists():
            raise PronunciationError(f"model vocab.json not found at {vocab_file}")
        try:
            raw = json.loads(vocab_file.read_text(encoding="utf-8"))
            # Keep the type coercion INSIDE the handler so a malformed vocab (a list/null, or
            # non-int ids) surfaces the specific "could not read model vocab.json" reason rather
            # than the generic load error from the caller's broad except.
            return {str(k): int(v) for k, v in raw.items()}
        except Exception as e:  # noqa: BLE001
            raise PronunciationError(f"could not read model vocab.json: {e}") from e

    # -- scoring ------------------------------------------------------------------
    def score(
        self,
        wav_path: Path,
        *,
        canonical: list[str],
        targets: list[dict],
        tip: str,
        competitors: list[str],
        drill_id: str,
        text: str,
        contrast_id: str,
    ) -> DrillResult:
        try:
            audio = self._read_audio(wav_path)
            if audio is None:
                return DrillResult(drill_id, text, contrast_id, "not_captured")
            self._load()
            logp = self._logits_to_logp(audio)
            return self._score_against_canonical(
                logp, canonical, targets, tip, competitors, drill_id, text, contrast_id
            )
        except PronunciationError as e:
            return DrillResult(drill_id, text, contrast_id, "error", detail=str(e))
        except Exception as e:  # noqa: BLE001 — never raise into the session
            return DrillResult(drill_id, text, contrast_id, "error", detail=str(e))

    # -- helpers ------------------------------------------------------------------
    @staticmethod
    def _read_audio(wav_path: Path) -> np.ndarray | None:
        import soundfile as sf

        data, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != _SAMPLE_RATE and data.size:
            from scipy.signal import resample  # repo's existing resample dep

            data = resample(data, int(round(len(data) * _SAMPLE_RATE / sr))).astype("float32")
        if data.size < _MIN_SPEECH_SECONDS * _SAMPLE_RATE:
            return None
        if float(np.sqrt(np.mean(np.square(data)))) < _MIN_SPEECH_RMS:
            return None
        return data

    def _logits_to_logp(self, audio: np.ndarray) -> np.ndarray:
        import torch

        inputs = self._feature_extractor(
            audio, sampling_rate=_SAMPLE_RATE, return_tensors="pt"
        )
        with torch.no_grad():
            logits = self._model(inputs.input_values).logits[0]  # [T, vocab]
        return torch.log_softmax(logits, dim=-1).cpu().numpy().astype(np.float64)

    def _score_against_canonical(
        self,
        logp: np.ndarray,
        canonical: list[str],
        targets: list[dict],
        tip: str,
        competitors: list[str],
        drill_id: str,
        text: str,
        contrast_id: str,
    ) -> DrillResult:
        id_of = self._sym2id
        # map canonical symbols → ids; drop unknowns, remembering the index remap so
        # `targets` still point at the right phone.
        canon_ids: list[int] = []
        old_to_new: dict[int, int] = {}
        for i, sym in enumerate(canonical):
            if sym in id_of:
                old_to_new[i] = len(canon_ids)
                canon_ids.append(int(id_of[sym]))
        if not canon_ids:
            return DrillResult(drill_id, text, contrast_id, "error", detail="no known phones")

        spans = gop.forced_align(canon_ids, logp, self._blank_id)
        scores = gop.gop_scores(canon_ids, spans, logp)
        comp_ids = {id_of[c] for c in competitors if c in id_of}

        flags: list[PhoneFlag] = []
        unscored_targets: list[str] = []
        for t in targets:
            old_idx = int(t["index"])
            if old_idx not in old_to_new:
                # The target phone itself is out-of-vocab: the model never evaluated the very
                # sound this drill teaches, so we must NOT return `scored` (empty flags renders
                # as a false "clear ✓"). Remember it; if NO target survived the vocab map, route
                # to the actionable `error` outcome the runner already surfaces/logs (IMP-007).
                unscored_targets.append(
                    canonical[old_idx] if 0 <= old_idx < len(canonical) else str(old_idx)
                )
                continue
            ni = old_to_new[old_idx]
            expected_sym = canonical[old_idx]
            expected_id = canon_ids[ni]
            g = scores[ni]
            comp_id, margin = gop.top_competitor(
                spans[ni], logp, self._blank_id, expected_id
            )
            comp_is_known_confusion = comp_id in comp_ids
            flagged = (
                g < _GOP_FLAG_THRESHOLD
                or margin > _COMPETITOR_FLAG_MARGIN
            )
            if not flagged:
                continue
            confident = margin >= _DIAGNOSIS_MARGIN and comp_is_known_confusion
            flags.append(
                PhoneFlag(
                    expected=expected_sym,
                    word=str(t.get("word", "")),
                    gop=round(float(g), 3),
                    competitor=self._id_to_sym(comp_id),
                    competitor_margin=round(float(margin), 3),
                    confident_diagnosis=confident,
                    tip=tip,
                )
            )
        if unscored_targets and len(unscored_targets) == len(targets):
            return DrillResult(
                drill_id,
                text,
                contrast_id,
                "error",
                detail=f"target phone(s) {unscored_targets!r} not in model vocab",
            )
        return DrillResult(drill_id, text, contrast_id, "scored", flags=flags)

    def _id_to_sym(self, idx: int) -> str | None:
        for sym, i in self._sym2id.items():
            if i == idx:
                return sym
        return None
