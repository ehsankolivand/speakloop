# installer

## Purpose

Model lifecycle: compute missing → consent → resumable download (aria2c when present,
else `snapshot_download` fallback) → re-validate. Owns the manifest, consent flow,
and download orchestration. Keeps the Mac awake via `caffeinate`. No engine packages.

## Public interface

- `ensure_models(phase, *, console=None, consent_fn=…, download_fn=…, input_fn=input)`
  — main orchestrator; raises `InstallDeclinedError` or `InstallFailedError`.
  Four `InstallFailedError` subclasses: `DownloadAuthError`, `DownloadNotFoundError`,
  `DownloadDiskError`, `ShardDiscoveryError`.
- `manifest.Model` (dataclass: name, hf_repo_id, expected_size_bytes, required_for_phase,
  `weight_files: tuple[str,...] | None` (016), local_path property). Named constants:
  `KOKORO_82M`, `WHISPER_LARGE_V3_TURBO`, `PARAKEET_TDT_06B_V3`, `QWEN3_14B_4BIT`, and
  `WAV2VEC2_PRONUNCIATION` (016 — opt-in, NOT in any PHASE_* list; `weight_files=
  ("pytorch_model.bin",)` because the repo ships no safetensors).
- `ensure_pronunciation_model(*, console, consent_fn, download_fn, input_fn)` (016) — same
  consent/caffeinate/download/validate lifecycle as `ensure_models`, for the single
  pronunciation model; fetched ONLY on first opt-in (FR-018/019). Shared body: `_ensure(...)`.
- `manifest.Phase` — `Literal["A", "B", "C"]`.
- `manifest.PHASE_A_MODELS`, `PHASE_B_MODELS`, `PHASE_C_MODELS` — typed `list[Model]`.
- `manifest.models_for_phase(phase) -> list[Model]`.
- `engine_needs_local_llm(engine, *, listen_only) -> bool` (015) — single source of truth for
  engine-aware provisioning: `engine == "local" and not listen_only`. The CLI ensures the base
  phase (A/B) always, then Phase C (Qwen) only when this is True; cloud engines never fetch it.
- `consent.prompt_for_consent(models) -> bool` — decline-by-default, size disclosure.
- `downloader.download_model(model)` — curl metadata → shard discovery → aria2c shards
  → outer retry; fallback to `huggingface_hub.snapshot_download(resume_download=True)`
  when aria2c absent. `spawn_caffeinate(console)` / `terminate_caffeinate(proc)` called
  once per install by `ensure_models`.
- `validator.validate(model) -> ValidationResult`.
  `ValidationResult` fields: `ok: bool`, `reason: Reason`, `measured_bytes: int`,
  `expected_bytes: int` (validator.py:14-18). `SIZE_TOLERANCE = 0.25` (±25%; validator.py:22).
  `reason` is one of `ok`/`missing`/`size_mismatch`/`incomplete`. `incomplete` (checked BEFORE
  the size test) fires when a `*.aria2` control file or a `*.incomplete` marker remains under
  `local_path` — a download killed past the tolerance would otherwise validate as complete and
  never resume; not-ok re-queues it so aria2 `--continue`/snapshot `resume_download` finish it (IMP-002).

## Dependencies & consumers

- Third-party: `huggingface_hub` (fallback path), `rich`.
- Internal: `speakloop.config` (model paths).
- System binaries: `aria2c` (optional, `brew install aria2`), `curl`, `caffeinate` (both macOS-native).
- Consumers: `asr`, `cli`, `llm`, `tts`.

## File map

- `manifest.py` — model constants, `PHASE_A/B/C_MODELS` lists, `models_for_phase()`.
- `consent.py` — user consent prompt with per-model size disclosure.
- `downloader.py` — per-model orchestrator: aria2 detection → curl metadata →
  `shards.discover_shards` → aria2 shard loop (retry `TRANSIENT_FAILURE`, raise
  `HARD_FAILURE`) → fallback `snapshot_download`. Also `spawn_caffeinate` /
  `terminate_caffeinate`.
- `aria.py` — `subprocess.Popen` wrapper for `aria2c`. `Aria2Outcome` enum
  (SUCCESS / TRANSIENT_FAILURE / HARD_FAILURE). `Aria2Progress` dataclass:
  bytes_received, bytes_total, download_rate_bps, eta_seconds, shard_filename.
  Only file that invokes `aria2c`.
- `tokens.py` — HF token resolver: env → `~/.cache/huggingface/token` → anonymous.
  Pure function; `__repr__` redacts the value.
- `shards.py` — parses `model.safetensors.index.json` → sorted shard list;
  single-file fallback `["model.safetensors"]`.
- `validator.py` — directory-size validation against `expected_size_bytes ± 25%`.

## Invariants & traps

- **aria2c flag values are pinned** in `contracts/downloader-cli-contract.md §8`
  (`--max-connection-per-server=16 --split=16 --min-split-size=1M --continue=true
  --max-tries=0 --retry-wait=5 --connect-timeout=30`). Changing any value requires
  updating the contract AND the test assertions in the same commit.
- **Token never leaves tokens.py** except through three call sites (curl `-H`,
  aria2c `--header=`, `snapshot_download(token=...)`). Must not appear in logs,
  repr, exception messages, or committed files.
- **Do not add a second parallel-download backend.** aria2c covers parallel streams,
  indefinite retry, and sleep prevention; a second backend fragments the path.
- **Fallback `snapshot_download` still passes `resume_download=True`** — no shard
  is re-downloaded from zero after an interruption.
- `expected_size_bytes` is approximate; the ±25% tolerance in `validator.py:22`
  covers imprecision until the measured byte sum replaces the estimate.

## Common modification patterns

- **Add/swap a model**: edit the `manifest.py` entry (id, repo, expected size) only. A repo
  with no safetensors index needs `weight_files=(...)` (016) so the downloader skips
  `discover_shards`; an opt-in model also adds a metadata file → extend `META_FILES`.
- **Change consent UX**: edit `consent.py`.
- **Tune aria2 concurrency / retry / connect-timeout**: update the pinned constants
  in the contract file AND the matching test assertions in the same commit.

## Pointers

- Root map: `CLAUDE.md`.
- Feature spec/plan: `specs/007-robust-model-download/`.
- Install-mechanism research: `doc/research_install.md`.
