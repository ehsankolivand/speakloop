# installer

Model presence, consent, resumable download, validation.

**Public surface**:

- `manifest.PHASE_A_MODELS`, `PHASE_B_MODELS`, `PHASE_C_MODELS`.
- `consent.prompt_for_consent(models) -> bool` (decline-by-default).
- `downloader.download_model(model)` wraps `huggingface_hub.snapshot_download(resume_download=True)`.
- `validator.validate(model) -> ValidationResult`.
- `ensure_models(phase)` orchestrator.

**Constitution Principle VI**: byte-range resume MUST be passed through to `snapshot_download`.
