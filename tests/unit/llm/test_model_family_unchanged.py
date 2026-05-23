"""V-R5 — the LLM is unchanged this sprint (contracts/report-invariance.md; FR-017).

The model stays `mlx-community/Qwen3-8B-4bit` — same FAMILY (Qwen3-8B) and same
QUANTIZATION (4-bit). 8-bit is out of scope (plan Decision 2: Constitution VI/VII
bandwidth/RAM). No swap; this guards against an accidental manifest change.
"""

from __future__ import annotations

import pytest

from speakloop.installer.manifest import QWEN3_8B_4BIT

pytestmark = pytest.mark.unit


def test_model_is_qwen3_8b_4bit():
    assert QWEN3_8B_4BIT.name == "Qwen3-8B-4bit"
    assert QWEN3_8B_4BIT.hf_repo_id == "mlx-community/Qwen3-8B-4bit"


def test_quantization_is_4bit_not_8bit():
    assert "4bit" in QWEN3_8B_4BIT.hf_repo_id
    assert "8bit" not in QWEN3_8B_4BIT.hf_repo_id  # 8-bit out of scope (Decision 2)


def test_family_is_qwen3_8b():
    # Family unchanged — not a different size or a VLM repo (root CLAUDE.md trap 3).
    assert "Qwen3-8B" in QWEN3_8B_4BIT.hf_repo_id
