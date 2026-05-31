"""T007 (007) — shard discovery from `model.safetensors.index.json`.

Contracts: `contracts/downloader-cli-contract.md §4`; data-model.md §ShardList.
"""

from __future__ import annotations

import json

import pytest

from speakloop.installer import ShardDiscoveryError
from speakloop.installer.shards import discover_shards

pytestmark = pytest.mark.unit


def test_returns_sorted_unique_shards_from_index(tmp_path):
    index = {
        "metadata": {"total_size": 123},
        "weight_map": {
            "model.layers.0.weight": "model-00002-of-00003.safetensors",
            "model.layers.1.weight": "model-00001-of-00003.safetensors",
            "model.layers.2.weight": "model-00003-of-00003.safetensors",
            "model.layers.3.weight": "model-00002-of-00003.safetensors",  # dup
        },
    }
    (tmp_path / "model.safetensors.index.json").write_text(json.dumps(index))

    assert discover_shards(tmp_path) == [
        "model-00001-of-00003.safetensors",
        "model-00002-of-00003.safetensors",
        "model-00003-of-00003.safetensors",
    ]


def test_single_file_fallback_when_no_index(tmp_path):
    assert discover_shards(tmp_path) == ["model.safetensors"]


def test_malformed_index_raises(tmp_path):
    (tmp_path / "model.safetensors.index.json").write_text("not json {{{")
    with pytest.raises(ShardDiscoveryError):
        discover_shards(tmp_path)


def test_empty_weight_map_raises(tmp_path):
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {}})
    )
    with pytest.raises(ShardDiscoveryError):
        discover_shards(tmp_path)


def test_missing_weight_map_key_raises(tmp_path):
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"metadata": {"total_size": 0}})
    )
    with pytest.raises(ShardDiscoveryError):
        discover_shards(tmp_path)


def test_weight_map_wrong_type_raises(tmp_path):
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": ["a.safetensors", "b.safetensors"]})
    )
    with pytest.raises(ShardDiscoveryError):
        discover_shards(tmp_path)
