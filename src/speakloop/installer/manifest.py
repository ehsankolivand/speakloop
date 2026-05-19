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
PARAKEET_TDT_06B_V3 = Model(
    name="Parakeet-TDT-0.6b-v3",
    hf_repo_id="mlx-community/parakeet-tdt-0.6b-v3",
    expected_size_bytes=2_509_044_141,  # measured 2.34 GB (7-file repo)
    required_for_phase="B",
)
# mlx-community's `Qwen3.5-9B-MLX-4bit` repos are vision-language models
# (`pipeline_tag: vision-language-model`, framework `mlx-vlm`) — incompatible
# with our `mlx_lm.load()` wrapper. The Phase-C use case is text-only grammar
# analysis on ASR transcripts, so we use the pure-text Qwen3-8B 4-bit build.
# Size = sum of every file in the repo (HF tree API, May 2026):
# 4,607,835,174 (model.safetensors) + 11,422,654 (tokenizer.json)
# + 2,776,833 (vocab.json) + 1,671,853 (merges.txt) + small configs.
QWEN3_8B_4BIT = Model(
    name="Qwen3-8B-4bit",
    hf_repo_id="mlx-community/Qwen3-8B-4bit",
    expected_size_bytes=4_623_784_971,  # ~4.31 GiB / 4.62 GB
    required_for_phase="C",
)


PHASE_A_MODELS: list[Model] = [KOKORO_82M]
PHASE_B_MODELS: list[Model] = [KOKORO_82M, PARAKEET_TDT_06B_V3]
PHASE_C_MODELS: list[Model] = [KOKORO_82M, PARAKEET_TDT_06B_V3, QWEN3_8B_4BIT]


def models_for_phase(phase: Phase) -> list[Model]:
    return {"A": PHASE_A_MODELS, "B": PHASE_B_MODELS, "C": PHASE_C_MODELS}[phase]
