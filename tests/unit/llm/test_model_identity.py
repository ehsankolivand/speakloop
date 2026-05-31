"""Pin the LLM manifest entry's identity.

The shipped model is `mlx-community/Qwen3-14B-4bit` (May 2026 swap from
Qwen3-8B-4bit, then re-quantised from 6-bit → 4-bit to fit the M3 Pro 18 GB
unified memory budget). Research and manifest agree on the Qwen3 14B family —
the prior Qwen3.5-9B-VLM divergence is closed (`doc/research_llm.md`).
"""

from __future__ import annotations

import pytest

from speakloop.installer.manifest import QWEN3_14B_4BIT

pytestmark = pytest.mark.unit


def test_model_is_qwen3_14b_4bit():
    assert QWEN3_14B_4BIT.name == "Qwen3-14B-4bit"
    assert QWEN3_14B_4BIT.hf_repo_id == "mlx-community/Qwen3-14B-4bit"


def test_required_for_phase_c():
    assert QWEN3_14B_4BIT.required_for_phase == "C"


def test_quantization_is_4bit():
    assert "4bit" in QWEN3_14B_4BIT.hf_repo_id
    assert "6bit" not in QWEN3_14B_4BIT.hf_repo_id
    assert "8bit" not in QWEN3_14B_4BIT.hf_repo_id


def test_family_is_qwen3_14b():
    assert "Qwen3-14B" in QWEN3_14B_4BIT.hf_repo_id
