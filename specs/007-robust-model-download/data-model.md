# Phase 1 Data Model: Resilient Model Downloads

**Feature**: 007-robust-model-download
**Plan**: [plan.md](plan.md)
**Research**: [research.md](research.md)

This feature is **mechanism-only**: no new persistent data, no schema_version
bump, no new YAML/JSON files written to disk that survive a session. The data
model below documents the small in-memory types added so the contracts can
reference them precisely.

## Persistent entities (unchanged)

The two persistent entities this feature touches already exist and are NOT
modified:

### `Model` (re-used as-is)

`src/speakloop/installer/manifest.py:Model` — a frozen dataclass with
`name: str`, `hf_repo_id: str`, `expected_size_bytes: int`, `required_for_phase:
Literal["A","B","C"]`, and the derived `local_path: Path` (under
`paths.models_dir()`). This feature reads `Model` but does NOT change its
shape, the per-model entries, or the per-phase lists.

### Model directory on disk (unchanged)

Per-model directory at `paths.models_dir() / slug`, where `slug =
hf_repo_id.replace("/", "__")`. Inside, the file set is the same as today:
metadata files (`config.json`, tokenizer files, etc.) plus the safetensors
shards listed in `model.safetensors.index.json` (or a single
`model.safetensors`). This feature changes how the files arrive on disk,
not which files exist or where.

## New in-memory types

These are private to `src/speakloop/installer/` and never serialized.

### `ResolvedToken` (new)

```python
@dataclass(frozen=True)
class ResolvedToken:
    value: str | None          # None ⇒ anonymous
    source: Literal["env", "hf_cli_file", "anonymous"]
```

- `value` is the raw token string when present, else `None`. Must never be
  logged, never appear in exception messages, never be passed through `repr()`
  of any other object that could end up in a stack trace.
- `source` is for diagnostic display only ("using token from $HF_TOKEN" vs.
  "using token from ~/.cache/huggingface/token" vs. "no token — anonymous").
  The token value itself never appears in that line.

Resolution: see [`contracts/token-resolution-contract.md`](contracts/token-resolution-contract.md).

### `ShardList` (new — alias)

```python
ShardList = list[str]   # filenames relative to the model directory
```

- The output of `shards.discover_shards(local_dir)`.
- Always sorted, always deduplicated.
- For a repo with `model.safetensors.index.json`: derived from the unique
  values of the `weight_map` field.
- For a repo without an index file: `["model.safetensors"]`.
- For a repo with an index file that parses but is empty/malformed:
  raise `ShardDiscoveryError` (FR-005 hard-error class — NOT a transient
  retryable condition).

### `Aria2Progress` (new)

```python
@dataclass(frozen=True)
class Aria2Progress:
    bytes_received: int
    bytes_total: int
    download_rate_bps: int      # 0 when unknown
    eta_seconds: int | None     # None when unknown / not yet stable
    shard_filename: str
```

- One snapshot per parsed aria2 status line.
- Pushed into a `rich.progress.Progress` task keyed by `(model_name,
  shard_filename)`.
- See [`contracts/progress-bridge-contract.md`](contracts/progress-bridge-contract.md)
  for the parsing grammar.

### `Aria2Outcome` (new)

```python
class Aria2Outcome(Enum):
    SUCCESS = "success"
    TRANSIENT_FAILURE = "transient"   # outer loop retries
    HARD_FAILURE = "hard"             # raise, no retry
```

Classification rules (from research Decision 3):

| Aria2 exit / log signal | Outcome | Reason |
|---|---|---|
| `aria2c` exit code 0 | `SUCCESS` | Shard fully downloaded. |
| Exit codes 1, 5, 6, 7 (network / DNS / connect / TLS) | `TRANSIENT_FAILURE` | Outer Python loop sleeps `retry_wait` seconds, respawns. |
| Exit code 22 + HTTP 401/403 | `HARD_FAILURE` | Bad / missing credential; raise `DownloadAuthError`. |
| Exit code 22 + HTTP 404 | `HARD_FAILURE` | Wrong repo or wrong filename; raise `DownloadNotFoundError`. |
| Exit code 9 (disk full / write error) | `HARD_FAILURE` | Raise `DownloadDiskError`. |
| Anything else | `TRANSIENT_FAILURE` | Conservative default — let the outer loop retry. |

The classification table is exhaustive and is the single source of truth for
FR-005 ("hard errors MUST NOT be swallowed by indefinite retry").

## Exceptions added

In `installer/__init__.py` alongside the existing `InstallDeclinedError`
and `InstallFailedError`:

- `DownloadAuthError(InstallFailedError)` — raised on 401/403; message names
  the credential precedence chain so the user knows where to fix.
- `DownloadNotFoundError(InstallFailedError)` — raised on 404; message names
  the offending URL (with the bearer token redacted).
- `DownloadDiskError(InstallFailedError)` — raised on disk-full / write
  errors; message gives the path under `paths.models_dir()`.
- `ShardDiscoveryError(InstallFailedError)` — raised on a malformed
  `model.safetensors.index.json`; message names the file path.

All four are subclasses of the existing `InstallFailedError` so callers that
already catch `InstallFailedError` continue to work unchanged.

## What is NOT in the data model

- No new on-disk file format. The `~/.speakloop/` layout is unchanged.
- No new config key in any YAML. The token is not configured anywhere
  speakloop owns; the HF CLI's standard file is the only "local config" path.
- No `schema_version` change to session reports. This feature does not
  touch `feedback/frontmatter.py`.
- No new HTTP server / port. aria2 is invoked as a subprocess in plain CLI
  mode, not RPC mode (research Decision 3).
