"""T027 — manifest model entries per data-model.md §9."""

from __future__ import annotations

import pytest

from speakloop.installer import manifest

pytestmark = pytest.mark.unit


def test_phase_a_has_tts_only():
    assert manifest.KOKORO_82M in manifest.PHASE_A_MODELS
    assert manifest.PARAKEET_TDT_06B_V3 not in manifest.PHASE_A_MODELS
    assert manifest.QWEN3_8B_4BIT not in manifest.PHASE_A_MODELS


def test_phase_b_adds_asr():
    assert manifest.KOKORO_82M in manifest.PHASE_B_MODELS
    assert manifest.PARAKEET_TDT_06B_V3 in manifest.PHASE_B_MODELS
    assert manifest.QWEN3_8B_4BIT not in manifest.PHASE_B_MODELS


def test_phase_c_adds_llm():
    assert manifest.KOKORO_82M in manifest.PHASE_C_MODELS
    assert manifest.PARAKEET_TDT_06B_V3 in manifest.PHASE_C_MODELS
    assert manifest.QWEN3_8B_4BIT in manifest.PHASE_C_MODELS


def test_each_model_has_required_fields():
    for m in manifest.PHASE_C_MODELS:
        assert m.name
        assert m.hf_repo_id
        assert m.expected_size_bytes > 0
        assert m.required_for_phase in {"A", "B", "C"}
        assert str(m.local_path)


def test_models_for_phase_selector():
    assert manifest.models_for_phase("A") == manifest.PHASE_A_MODELS
    assert manifest.models_for_phase("B") == manifest.PHASE_B_MODELS
    assert manifest.models_for_phase("C") == manifest.PHASE_C_MODELS
