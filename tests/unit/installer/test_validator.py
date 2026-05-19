"""T030 — validator size/missing checks (FR-022)."""

from __future__ import annotations

import pytest

from speakloop.installer import manifest, validator

pytestmark = pytest.mark.unit


def _write_n_bytes(path, n_bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * n_bytes)


def test_missing_returns_missing(tmp_models_dir):
    result = validator.validate(manifest.KOKORO_82M)
    assert result.ok is False
    assert result.reason == "missing"


def test_matching_size_returns_ok(tmp_models_dir):
    p = manifest.KOKORO_82M.local_path
    _write_n_bytes(p / "weights.bin", manifest.KOKORO_82M.expected_size_bytes)
    result = validator.validate(manifest.KOKORO_82M)
    assert result.ok is True
    assert result.reason == "ok"


def test_undersize_returns_size_mismatch(tmp_models_dir):
    p = manifest.KOKORO_82M.local_path
    # 50% of expected — below the 25% tolerance floor.
    _write_n_bytes(p / "weights.bin", manifest.KOKORO_82M.expected_size_bytes // 2)
    result = validator.validate(manifest.KOKORO_82M)
    assert result.ok is False
    assert result.reason == "size_mismatch"


def test_empty_dir_treated_as_missing(tmp_models_dir):
    manifest.KOKORO_82M.local_path.mkdir(parents=True, exist_ok=True)
    result = validator.validate(manifest.KOKORO_82M)
    assert result.ok is False
    assert result.reason == "missing"
