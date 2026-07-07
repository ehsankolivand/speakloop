"""Live smoke for the DEFAULT feedback engine — the real local Qwen3-14B-4bit (mlx_lm).

The `QwenEngine` unit tests (`tests/unit/llm/test_qwen_engine.py`) fabricate a fake `mlx_lm`
module and assert the wrapper calls `make_sampler(...)` / `make_logits_processors(...)` /
`generate(...)` a certain way — so they validate the wrapper against the test's OWN fake,
never against the real package. An `mlx_lm` bump that dropped `sampler=` or renamed a kwarg
would break every local session while the mocked suite stayed green. This is the only local
model path with no real-model harness (ASR, cloud, downloader, pronunciation each have one).

This test closes that gap: it loads the REAL Qwen through `QwenEngine` and does one tiny
generate, plus calls the real `make_sampler`/`make_logits_processors` with the exact kwargs
the wrapper (and the fakes) assume — so an API drift fails loudly HERE.

HEAVY (loads the ~8 GB model) and EXCLUDED from the default suite (`addopts: -m
'... and not live_llm'`). It self-skips when the model / `mlx_lm` are absent, mirroring
`live_pron` / `live_asr`, so it never loads a model in CI. Run it explicitly on a
model-equipped machine:

    uv run pytest -m live_llm -v
"""

from __future__ import annotations

import pytest

from speakloop.installer import manifest, validator

pytestmark = pytest.mark.live_llm


def _model_ready() -> bool:
    return validator.validate(manifest.QWEN3_14B_4BIT).ok


@pytest.mark.skipif(
    not _model_ready(),
    reason="Qwen3-14B-4bit not downloaded — run `speakloop practice` (local engine) first",
)
def test_real_mlx_lm_sampler_and_generate_api_matches_the_wrapper():
    pytest.importorskip("mlx_lm")

    from mlx_lm.sample_utils import make_logits_processors, make_sampler

    # The wrapper (qwen_engine.generate) builds the sampler + logits processors with exactly
    # these kwargs; calling them here proves the real API still accepts them (the fakes assume
    # this). A signature drift raises TypeError right here, pinpointing the drifted function.
    sampler = make_sampler(temp=0.3, top_p=0.8, top_k=20, min_p=0.0)
    assert callable(sampler)
    processors = make_logits_processors(repetition_penalty=1.05, repetition_context_size=40)
    assert isinstance(processors, list)

    from speakloop.llm.qwen_engine import QwenEngine

    # End-to-end: load the real model and run one tiny generation through the full wrapper
    # (load → build_prompt → make_sampler → generate(sampler=, logits_processors=, max_tokens=)
    # → strip <think>). A non-empty string means every real kwarg the fakes assume was accepted.
    engine = QwenEngine()
    out = engine.generate(
        "You are a terse assistant. Reply with a single word.",
        "Say the word: ok",
        max_tokens=8,
        temperature=0.3,
    )
    assert isinstance(out, str)
    assert out.strip(), "the real Qwen generate returned empty output"
