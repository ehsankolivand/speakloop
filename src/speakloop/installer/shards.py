"""Shard discovery for HuggingFace safetensors repos (007).

Parses `model.safetensors.index.json` into a sorted-unique list of shard
filenames; falls back to `["model.safetensors"]` when no index exists.

Contract: `specs/007-robust-model-download/contracts/downloader-cli-contract.md §4`.
"""

from __future__ import annotations

import json
from pathlib import Path

from speakloop.installer import ShardDiscoveryError

ShardList = list[str]

_INDEX_FILENAME = "model.safetensors.index.json"
_SINGLE_FILE_FALLBACK = "model.safetensors"


def discover_shards(local_dir: Path) -> ShardList:
    """Return the sorted-unique list of safetensors shard filenames to download.

    Rules (per contract §4):
      1. If `local_dir / model.safetensors.index.json` exists, parse it and
         return `sorted(set(data["weight_map"].values()))`.
      2. Otherwise return `["model.safetensors"]`.

    Raises `ShardDiscoveryError` when the index is malformed, when `weight_map`
    is missing / wrong type, or when `weight_map` is empty.
    """
    index_path = Path(local_dir) / _INDEX_FILENAME
    if not index_path.exists():
        return [_SINGLE_FILE_FALLBACK]

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ShardDiscoveryError(f"could not parse {index_path}: {exc}") from exc

    weight_map = data.get("weight_map") if isinstance(data, dict) else None
    if not isinstance(weight_map, dict):
        raise ShardDiscoveryError(
            f"missing or non-dict 'weight_map' in {index_path}"
        )
    shards = sorted({v for v in weight_map.values() if isinstance(v, str)})
    if not shards:
        raise ShardDiscoveryError(f"'weight_map' in {index_path} is empty")
    return shards
