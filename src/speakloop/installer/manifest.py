"""Per-phase model manifest.

The ONLY file that needs editing on an engine swap at the manifest level
(Principle V; the wrapper file change is separate).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from speakloop.config import paths

Phase = Literal["A", "B", "C"]


@dataclass(frozen=True)
class Model:
    name: str
    hf_repo_id: str
    expected_size_bytes: int
    required_for_phase: Phase
    # 016: explicit weight filenames for repos that DON'T ship safetensors (so the
    # downloader skips `discover_shards`, which would 404 on a missing model.safetensors).
    # None ⇒ today's behavior (discover safetensors shards). Additive; existing models
    # leave it None so their aria2 invocation is byte-identical.
    weight_files: tuple[str, ...] | None = None

    @property
    def local_path(self) -> Path:
        slug = self.hf_repo_id.replace("/", "__")
        return paths.models_dir() / slug


# Approximate sizes from doc/research_{tts,asr,llm}.md.
# Kokoro: kokoro_mlx requires the mlx-community safetensors build — the
# original hexgrad PyTorch repo only ships .pth weights and is not loadable
# by kokoro_mlx.KokoroTTS.from_pretrained().
KOKORO_82M = Model(
    name="Kokoro-82M",
    hf_repo_id="mlx-community/Kokoro-82M-bf16",
    expected_size_bytes=170 * 1024 * 1024,  # ~170 MB bf16
    required_for_phase="A",
)
# 003-asr-l2-accent-accuracy: the new DEFAULT ASR (research_asr_l2_accent.md §B.2 —
# L2-ARCTIC 5.4% MER, `initial_prompt` biasing lever). Parakeet stays below as the
# `--asr-engine parakeet` opt-in + automatic load-failure fallback (Principle V).
WHISPER_LARGE_V3_TURBO = Model(
    name="Whisper-large-v3-turbo",
    hf_repo_id="mlx-community/whisper-large-v3-turbo",
    expected_size_bytes=1_613_979_758,  # measured 1.50 GiB (HF tree API, 2026-05)
    required_for_phase="B",
)
PARAKEET_TDT_06B_V3 = Model(
    name="Parakeet-TDT-0.6b-v3",
    hf_repo_id="mlx-community/parakeet-tdt-0.6b-v3",
    expected_size_bytes=2_509_044_141,  # measured 2.34 GB (7-file repo)
    required_for_phase="B",
)
# Qwen3-14B at MLX 4-bit (~7-8 GB on disk). The native Qwen3 chat template
# supports `enable_thinking=True`; the wrapper (llm/qwen_engine.py) strips the
# leading `<think>...</think>` block at the boundary so downstream code parses
# clean JSON. Pre-adoption testing on a Persian-L1 transcript triple showed
# the 14B family reached 7/7 recall and was the only candidate to distinguish
# present continuous from present simple (vs Granite-4.1-8B and Ministral-3-
# 14B-Instruct). 4-bit (not 6-bit) is the right precision for the M3 Pro 18 GB
# target: the 6-bit variant (~12 GB on-disk, ~14 GB resident) exceeded unified
# memory when loaded alongside the resident Whisper-large-v3-turbo encoder.
# Research divergence (the original Qwen3.5-9B VLM trap) remains CLOSED —
# doc/research_llm.md agrees with the manifest on the Qwen3 family at 14B.
# TODO: replace expected_size_bytes with the measured byte sum from the HF
# tree once the model is downloaded; the validator's ±25% tolerance
# (installer/validator.py:22) covers the imprecision in the meantime.
QWEN3_14B_4BIT = Model(
    name="Qwen3-14B-4bit",
    hf_repo_id="mlx-community/Qwen3-14B-4bit",
    expected_size_bytes=8_000_000_000,  # ~8 GB; refine after first download.
    required_for_phase="C",
)


# 016-pronunciation-drills: the optional read-aloud pronunciation scorer's acoustic model
# (wav2vec2 CTC phoneme recognizer, Apache-2.0). NOT in any PHASE_*_MODELS list — it is
# fetched ONLY on first opt-in via `ensure_pronunciation_model`, never by a phase. The repo
# ships a single `pytorch_model.bin` with NO safetensors index, so `weight_files` is set so
# the downloader fetches that file directly (research D3/D6; verified against the HF tree).
# `required_for_phase` is a valid literal purely to satisfy the dataclass; it is never used
# for provisioning (the model is not in any phase list).
WAV2VEC2_PRONUNCIATION = Model(
    name="wav2vec2-phoneme-en",
    hf_repo_id="facebook/wav2vec2-lv-60-espeak-cv-ft",
    expected_size_bytes=1_262_000_000,  # ~1.26 GB single pytorch_model.bin (±25% tolerance)
    required_for_phase="C",
    weight_files=("pytorch_model.bin",),
)


PHASE_A_MODELS: list[Model] = [KOKORO_82M]
# Whisper is the default ASR; Parakeet is downloaded too so the runtime fallback
# (FR-009/SC-F) and `--asr-engine parakeet` always have a model present.
PHASE_B_MODELS: list[Model] = [KOKORO_82M, WHISPER_LARGE_V3_TURBO, PARAKEET_TDT_06B_V3]
PHASE_C_MODELS: list[Model] = [
    KOKORO_82M,
    WHISPER_LARGE_V3_TURBO,
    PARAKEET_TDT_06B_V3,
    QWEN3_14B_4BIT,
]


def models_for_phase(phase: Phase) -> list[Model]:
    return {"A": PHASE_A_MODELS, "B": PHASE_B_MODELS, "C": PHASE_C_MODELS}[phase]
