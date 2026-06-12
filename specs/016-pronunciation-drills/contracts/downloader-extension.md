# Contract: downloader extension for a single-file (non-safetensors) model

Extends feature 007's aria2 downloader **in place** (FR-019/FR-020). No second backend, no bespoke
path. The only reason an extension is needed: `facebook/wav2vec2-lv-60-espeak-cv-ft` ships a single
`pytorch_model.bin` (no `model.safetensors`, no shard index), and needs `preprocessor_config.json`.

## Change 1 — `manifest.Model.weight_files`

Add an optional field (additive; defaults preserve today's behavior for every existing model):

```python
@dataclass(frozen=True)
class Model:
    name: str
    hf_repo_id: str
    expected_size_bytes: int
    required_for_phase: Phase
    weight_files: tuple[str, ...] | None = None   # explicit weight filenames; None ⇒ discover_shards()
```

## Change 2 — `downloader._download_via_aria` shard source

```python
shards = list(model.weight_files) if model.weight_files else discover_shards(local_dir)
```

- When `weight_files` is `None` (all existing models): behavior is **byte-identical** — discovery via
  `model.safetensors.index.json` with the `["model.safetensors"]` fallback, same aria2 flags.
- When set (the pronunciation model): download exactly those files (`("pytorch_model.bin",)`), each via
  the same `_HF_BASE/<repo>/resolve/main/<file>` URL, the same pinned aria2 flags, the same outer
  retry / transient-vs-hard classification, and the same `snapshot_download(resume_download=True)`
  fallback when `aria2c` is absent. Resumable (`--continue=true`).

## Change 3 — `downloader.META_FILES`

Add `"preprocessor_config.json"` to the tuple. It is fetched best-effort (curl `-f`); repos without it
skip it silently ("not in repo, skipping"), so no existing model's metadata set changes meaningfully.
`vocab.json`, `config.json`, `tokenizer_config.json`, `special_tokens_map.json` are already present.

## Change 4 — `installer.ensure_pronunciation_model(...)`

```python
def ensure_pronunciation_model(*, console=None, consent_fn=_consent.prompt_for_consent,
                               download_fn=downloader.download_model, input_fn=input) -> None:
    """Ensure the pronunciation model is present. Mirrors ensure_models() for the single
    WAV2VEC2_PRONUNCIATION model: validate → (caffeinate) → consent (size disclosure) → download →
    re-validate. Raises InstallDeclinedError / InstallFailedError exactly like ensure_models()."""
```

Reuses the existing `consent.prompt_for_consent` (size + target path disclosure, decline-by-default),
`spawn_caffeinate`/`terminate_caffeinate` wakelock, and `validator.validate` (dir size ±25%). The CLI
calls it only after the gate is SAFE (or an override is confirmed) and the user opted in.

## Tests (`tests/unit/installer/test_pronunciation_model.py`)

1. `WAV2VEC2_PRONUNCIATION.weight_files == ("pytorch_model.bin",)` and it is **not** in any
   `PHASE_*_MODELS` list.
2. With a fake aria runner, downloading the model requests `pytorch_model.bin` (from `weight_files`),
   **not** `model.safetensors` (proving `discover_shards` was bypassed).
3. `preprocessor_config.json` is in `META_FILES`.
4. `ensure_pronunciation_model` honors decline (`InstallDeclinedError`) and a fake `download_fn` (no
   network), and re-validates afterward.
5. Existing-model regression: a model with `weight_files=None` still resolves shards via
   `discover_shards` (no behavior change) — covered by the existing 007 downloader tests staying green.
