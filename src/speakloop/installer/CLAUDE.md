# installer

## Purpose

Model lifecycle: compute missing → consent → resumable download (aria2c when present, else
`snapshot_download` fallback) → re-validate. Keeps the Mac awake via `caffeinate` for the
duration of `ensure_models(...)`. Owns the model manifest (which model build each phase
needs) and the consent flow. No engine packages here.

## Public interface

- `ensure_models(phase, *, console=None, consent_fn=…, download_fn=…, input_fn=input)` — the
  orchestrator; raises `InstallDeclinedError` (user declines) or `InstallFailedError`
  (validation still fails after download). The four 007-typed subclasses of
  `InstallFailedError` — `DownloadAuthError`, `DownloadNotFoundError`, `DownloadDiskError`,
  `ShardDiscoveryError` — propagate from the new download path.
- `manifest` — `Model`, `Phase`, `models_for_phase(phase)`, the per-phase model lists.
- `consent.prompt_for_consent(models) -> bool` (decline-by-default, size disclosure).
- `downloader.download_model(model)` — orchestrates curl-for-metadata, shard discovery,
  aria2c-for-shards, indefinite outer retry, caffeinate; falls back to
  `huggingface_hub.snapshot_download(resume_download=True)` when `aria2c` is missing.
- `validator.validate(model) -> ValidationResult`.

## Dependencies

- Third-party (Python): `huggingface_hub` (fallback path only), `rich`. Internal:
  `speakloop.config` (model paths).
- System binaries: `aria2c` (`brew install aria2`, optional — fallback path runs without
  it), `curl` (ships with macOS), `caffeinate` (ships with macOS).

## Consumers

`asr`, `cli`, `llm`, `tts` (each ensures/locates its model via the manifest).

## File map

- `manifest.py` — model definitions incl. the Qwen3-14B-4bit entry and thinking-on
  rationale (see `doc/research_llm.md` May 2026 update). 4-bit (not 6-bit) is the
  right precision for the M3 Pro 18 GB target — the 6-bit variant exceeded unified
  memory alongside the resident Whisper encoder.
- `consent.py` — consent prompt with per-model size disclosure.
- `downloader.py` — per-model orchestrator: detect aria2 → curl metadata pass →
  `shards.discover_shards` → aria2 shard loop (outer retry on `TRANSIENT_FAILURE`,
  raise on `HARD_FAILURE`) → on missing aria2, one-line yellow warning +
  `huggingface_hub.snapshot_download(resume_download=True, token=…)`. Exposes
  `spawn_caffeinate(console) -> Popen|None` and `terminate_caffeinate(proc)`,
  which `ensure_models(...)` calls once per install (contract §2).
- `aria.py` — `subprocess.Popen` wrapper around `aria2c`: parses progress lines,
  classifies the exit code into `Aria2Outcome` (SUCCESS / TRANSIENT_FAILURE /
  HARD_FAILURE), bridges progress into Rich. Only this file invokes `aria2c`.
- `tokens.py` — env > `~/.cache/huggingface/token` > anonymous resolver. Pure
  function, no I/O at import time, `__repr__` redacts the token value.
- `shards.py` — parses `model.safetensors.index.json` → sorted unique shard list;
  single-file fallback `["model.safetensors"]` when no index exists.
- `validator.py` — byte-size/presence validation.

## Common modification patterns

- **Add/swap a model build**: edit the `manifest.py` entry (id, repo, expected size) only.
- **Change consent UX**: edit `consent.py`.
- **Tune aria2 concurrency / retry / connect-timeout**: edit the pinned constants
  in `contracts/downloader-cli-contract.md §8` AND the matching assertions in
  `tests/unit/installer/test_downloader.py` / `test_aria.py` in the same commit.

## Constitution Principle VIII justification (007)

`brew install aria2` is a non-Python prerequisite — friction Principle VIII explicitly
minimises. Justified because aria2 is the mechanism that delivers FR-001/-002/-003
(parallel streams + byte-accurate resume + indefinite retry) on the user's already-
validated configuration (`download_aria.sh`). Friction is mitigated by:

- **Auto-fallback** (FR-019): no aria2 on `PATH` ⇒ `snapshot_download(resume_download=
  True)` keeps `git clone && uv run speakloop` working at parity with today.
- **`speakloop doctor`** surfaces the missing tool with the exact `brew install aria2`
  command (Principle VIII's "guide the user" intent).
- **README** lists `brew install aria2` immediately after the `uv` prerequisite.

See `specs/007-robust-model-download/plan.md § Complexity Tracking` and
`doc/research_install.md` for the full decision trail.

## Traps

- **Byte-range resume is delivered by aria2c's `--continue=true`** (formerly by
  `snapshot_download(resume_download=True)`); the fallback path STILL passes
  `resume_download=True` for the snapshot_download branch. Either way, no shard is
  re-downloaded from zero after an interruption (Constitution Principle VI).
- **`aria2c` flag values are pinned** in `contracts/downloader-cli-contract.md §8`
  (`--max-connection-per-server=16 --split=16 --min-split-size=1M --continue=true
  --max-tries=0 --retry-wait=5 --connect-timeout=30`). Don't change a value
  in code without updating the contract AND the test assertions in the same commit.
- **Don't add a second parallel-download backend.** `hf-transfer` was removed in
  feature 007 because the chosen mechanism (aria2c) already covers parallel byte-
  range streams AND indefinite retry AND sleep prevention; a second backend would
  re-fragment the path.
- **The token value never leaves `tokens.py` except through three call sites**
  (curl `-H Authorization: Bearer …`, aria2c `--header=Authorization: Bearer …`,
  `snapshot_download(token=…)`). It must NOT appear in logs, `repr()`, exception
  messages, or any committed file. The HF token format `r"\bhf_[A-Za-z0-9]{20,}\b"`
  is scanned by `tests/integration/test_path_portability_audit.py`.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md).
- Feature spec/plan: [`../../../specs/007-robust-model-download/`](../../../specs/007-robust-model-download/).
- Install-mechanism research: [`../../../doc/research_install.md`](../../../doc/research_install.md).
