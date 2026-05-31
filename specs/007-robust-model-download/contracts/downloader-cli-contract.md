# Contract: Downloader CLI Invocations

**Feature**: 007-robust-model-download
**Module**: `src/speakloop/installer/` (`downloader.py` + new `aria.py`)
**Test files**: `tests/unit/installer/test_downloader.py`,
`tests/unit/installer/test_aria.py`, `tests/unit/installer/test_shards.py`

This contract pins the exact subprocess invocations the new downloader emits.
Tests assert against this contract; the implementation MUST conform.

## 1. Pre-flight: detect `aria2c`

```python
import shutil
ARIA2_BIN: str | None = shutil.which("aria2c")
```

- If `ARIA2_BIN is None`: fall through to the snapshot_download fallback path
  (see §6). Emit exactly ONE warning line to the installer console:
  `[yellow]aria2 not found — using single-connection fallback. Install with: brew install aria2[/yellow]`
- If `ARIA2_BIN` resolves: continue with the aria2 path below.

## 2. Caffeinate (macOS sleep prevention)

```python
caffeinate_proc = subprocess.Popen(
    ["caffeinate", "-dimsu", "-w", str(os.getpid())],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```

- Spawned at the entry of `ensure_models(...)`, BEFORE the consent prompt.
- Always paired with `try/finally` cleanup: `caffeinate_proc.terminate()`
  inside `finally`, plus an `atexit` handler as defense in depth.
- If `Popen` raises `FileNotFoundError` (caffeinate missing — non-macOS or
  sandbox), emit one warning line and continue: `[yellow]caffeinate not found — sleep prevention disabled.[/yellow]`

## 3. Metadata pass (curl)

For each name in the metadata file set:

```python
META_FILES = (
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
    "generation_config.json",
    "chat_template.jinja",
    "model.safetensors.index.json",
    "README.md",
)
```

Invocation:

```python
cmd = [
    "curl", "-L", "-f", "-s",
    "-o", str(local_dir / name),
    "--retry", "5",
    "--retry-delay", "3",
    f"https://huggingface.co/{repo_id}/resolve/main/{name}",
]
if token is not None:
    # Insert BEFORE the URL; -H may appear once or many times.
    cmd[1:1] = ["-H", f"Authorization: Bearer {token}"]
```

Pass / fail handling:
- `returncode == 0`: file present in repo and downloaded. Log `ok`.
- `returncode != 0` (HTTP 404 most commonly): file not in this repo. Delete
  the empty/partial file, log `(not in repo, skipping)`, continue. This is
  NOT an error — many HF repos do not ship every member of `META_FILES`.

## 4. Shard discovery

```python
from speakloop.installer.shards import discover_shards
shards: ShardList = discover_shards(local_dir)
```

`discover_shards(local_dir)` rules (deterministic, pure function):
1. If `local_dir / "model.safetensors.index.json"` exists:
   - Open and `json.loads(...)` it.
   - Read `data["weight_map"]` — expected to be `dict[str, str]` mapping
     tensor name → shard filename.
   - Return `sorted(set(data["weight_map"].values()))`.
   - If `weight_map` is missing or not a dict, raise
     `ShardDiscoveryError`.
2. Else, return `["model.safetensors"]` (single-file fallback).

## 5. Shard pass (aria2c, one shard at a time, indefinite outer-loop retry)

For each `shard` in `shards`:

```python
url = f"https://huggingface.co/{repo_id}/resolve/main/{shard}"
cmd = [
    ARIA2_BIN,
    "--max-connection-per-server=16",
    "--split=16",
    "--min-split-size=1M",
    "--continue=true",
    "--max-tries=0",
    "--retry-wait=5",
    "--connect-timeout=30",
    f"--out={shard}",
    f"--dir={local_dir}",
    url,
]
if token is not None:
    cmd.insert(1, f"--header=Authorization: Bearer {token}")
```

Outer Python loop (FR-003 indefinite retry):

```python
while True:
    outcome = aria.run(cmd, on_progress=progress_bridge)
    if outcome is Aria2Outcome.SUCCESS:
        break
    if outcome is Aria2Outcome.HARD_FAILURE:
        raise <the typed error already constructed by aria.run>
    # Aria2Outcome.TRANSIENT_FAILURE
    console.print(f"[yellow]Connection lost — retrying in 10s…[/yellow]")
    time.sleep(10)
```

- The `--max-tries=0` flag means aria2 itself retries forever within a
  single invocation; the outer Python loop is the second tier (defense
  against aria2 crashing entirely or being killed).
- `time.sleep(10)` here mirrors the `download_aria.sh` `sleep 10` and is the
  outer-loop backoff; aria2's `--retry-wait=5` is the inner backoff.

## 6. Fallback path (aria2 missing)

When `ARIA2_BIN is None`:

```python
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id=model.hf_repo_id,
    local_dir=str(model.local_path),
    resume_download=True,
    token=token,                     # None ⇒ anonymous
)
```

- No metadata-vs-shard split; snapshot_download fetches the whole repo.
- The `token` kwarg is set to the resolved value (or `None`); this is the
  HuggingFace Hub SDK's documented anonymous-vs-authenticated path.
- The single warning line in §1 is the only user-visible difference from
  the aria2 path; the rest of `ensure_models(...)` (consent, validation)
  runs identically.

## 7. Post-download

For each model that finished §5 or §6:

```python
result = validator.validate(model)
if not result.ok:
    raise InstallFailedError(...)   # existing message format, unchanged
```

Validation is byte-size + presence with the existing ±25% tolerance
(`installer/validator.py`). Unchanged.

## 8. Constants pinned by this contract

| Symbol | Value | Source |
|---|---|---|
| `MAX_CONNECTIONS_PER_SERVER` | `16` | `download_aria.sh` |
| `SPLIT` | `16` | `download_aria.sh` |
| `MIN_SPLIT_SIZE` | `1M` | `download_aria.sh` |
| `ARIA2_INNER_RETRY_WAIT_SEC` | `5` | `download_aria.sh` |
| `ARIA2_CONNECT_TIMEOUT_SEC` | `30` | `download_aria.sh` |
| `PYTHON_OUTER_RETRY_WAIT_SEC` | `10` | `download_aria.sh` |
| `CURL_RETRY_COUNT` | `5` | `download_aria.sh` |
| `CURL_RETRY_DELAY_SEC` | `3` | `download_aria.sh` |

Changing any of these requires updating this contract AND the unit tests in
`test_downloader.py` / `test_aria.py`. They are not user-tunable in v1
(see Assumption: "concurrency is bounded, not configurable").
