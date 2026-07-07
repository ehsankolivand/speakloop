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


def test_leftover_aria2_control_file_is_incomplete(tmp_models_dir):
    """IMP-002: a download killed past the size tolerance still leaves a `.aria2`
    control file — it must not validate as complete, or resume never runs."""
    p = manifest.KOKORO_82M.local_path
    # Enough bytes to clear the 25% floor, so only the sidecar reveals the truncation.
    _write_n_bytes(p / "model.safetensors", manifest.KOKORO_82M.expected_size_bytes)
    _write_n_bytes(p / "model.safetensors.aria2", 512)
    result = validator.validate(manifest.KOKORO_82M)
    assert result.ok is False
    assert result.reason == "incomplete"


def test_leftover_incomplete_marker_is_incomplete(tmp_models_dir):
    """IMP-002: `snapshot_download`'s `*.incomplete` marker also blocks a false OK."""
    p = manifest.KOKORO_82M.local_path
    _write_n_bytes(p / "model.safetensors", manifest.KOKORO_82M.expected_size_bytes)
    _write_n_bytes(p / ".cache" / "huggingface" / "download" / "weights.incomplete", 8)
    result = validator.validate(manifest.KOKORO_82M)
    assert result.ok is False
    assert result.reason == "incomplete"


def test_clear_incomplete_markers_lets_a_completed_download_validate(tmp_models_dir):
    """BUG-001: a stale CROSS-BACKEND marker (aria2's `.aria2` finished by snapshot, or a
    snapshot `.incomplete` finished by aria2) must not pin a complete model as `incomplete`
    forever. Once the download completes, clearing the markers restores a clean OK."""
    p = manifest.KOKORO_82M.local_path
    _write_n_bytes(p / "model.safetensors", manifest.KOKORO_82M.expected_size_bytes)
    _write_n_bytes(p / "model.safetensors.aria2", 512)
    _write_n_bytes(p / ".cache" / "huggingface" / "download" / "weights.incomplete", 8)
    # Before: the leftover markers make an otherwise-complete directory validate as incomplete.
    assert validator.validate(manifest.KOKORO_82M).reason == "incomplete"

    validator.clear_incomplete_markers(p)

    # After: the markers are gone and the complete bytes validate OK — no permanent loop.
    result = validator.validate(manifest.KOKORO_82M)
    assert result.ok is True
    assert result.reason == "ok"
    assert not (p / "model.safetensors.aria2").exists()
    assert not (p / ".cache" / "huggingface" / "download" / "weights.incomplete").exists()
    assert (p / "model.safetensors").exists()  # the real weights are untouched


def test_clear_incomplete_markers_is_a_noop_when_none_remain(tmp_models_dir):
    """A clean, complete directory is untouched (a same-backend resume already removed
    its own marker) — the clear step never disturbs real weights."""
    p = manifest.KOKORO_82M.local_path
    _write_n_bytes(p / "model.safetensors", manifest.KOKORO_82M.expected_size_bytes)
    validator.clear_incomplete_markers(p)
    assert validator.validate(manifest.KOKORO_82M).ok is True
