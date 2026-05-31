# installer

## Purpose

Model lifecycle: compute missing → consent → resumable download → re-validate. Owns the model
manifest (which model build each phase needs) and the consent flow. No engine packages here.

## Public interface

- `ensure_models(phase, *, console=None, consent_fn=…, download_fn=…, input_fn=input)` — the
  orchestrator; raises `InstallDeclinedError` (user declines) or `InstallFailedError`
  (validation still fails after download).
- `manifest` — `Model`, `Phase`, `models_for_phase(phase)`, the per-phase model lists.
- `consent.prompt_for_consent(models) -> bool` (decline-by-default, size disclosure).
- `downloader.download_model(model)` — wraps `huggingface_hub.snapshot_download(resume_download=True)`.
- `validator.validate(model) -> ValidationResult`.

## Dependencies

- Third-party: `huggingface_hub`, `rich`. Internal: `speakloop.config` (model paths).

## Consumers

`asr`, `cli`, `llm`, `tts` (each ensures/locates its model via the manifest).

## File map

- `manifest.py` — model definitions incl. the Qwen3-14B-4bit entry and thinking-on
  rationale (see `doc/research_llm.md` May 2026 update). 4-bit (not 6-bit) is the
  right precision for the M3 Pro 18 GB target — the 6-bit variant exceeded unified
  memory alongside the resident Whisper encoder.
- `consent.py` — consent prompt with per-model size disclosure.
- `downloader.py` — resumable `snapshot_download`.
- `validator.py` — byte-size/presence validation.

## Common modification patterns

- **Add/swap a model build**: edit the `manifest.py` entry (id, repo, expected size) only.
- **Change consent UX**: edit `consent.py`.

## Traps

- **Byte-range resume MUST be passed through** to `snapshot_download` (`resume_download=True`) —
  Constitution Principle VI; the target user has unreliable internet.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md).
