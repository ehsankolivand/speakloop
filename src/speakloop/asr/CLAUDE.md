# asr

Speech-to-text engine wrapper. Default engine **Whisper-large-v3-turbo**
(mlx-whisper) with per-session domain biasing + Silero-VAD pre-segmentation;
Parakeet-TDT kept as `--asr-engine parakeet` and automatic load-failure fallback
(003-asr-l2-accent-accuracy; compass `doc/research_asr_l2_accent.md`).

**Public surface**:

- `interface.ASREngine` (Protocol) — `transcribe(wav_path, *, context=None) -> Transcript`
  and `ensure_loaded()`. The `context` keyword is additive/optional.
- `interface.Transcript`, `interface.WordTiming`, `interface.ASREngineError`.
- `interface.TranscriptionContext` — per-session biasing payload
  (`initial_prompt`, `initial_prompt_sha256`, `use_vad`).
- `selection.build_engine(name=None) -> EngineSelection` — resolves the default
  Whisper or the requested engine, probes the load eagerly, and falls back to
  Parakeet with one English reason on load failure (FR-002/FR-009/SC-F). Imports
  the wrapper classes only — no third-party engine package (Principle V).
- `domain_context.build_context(question) -> TranscriptionContext` — mines the
  question + ideal answer + tags, adds the `seed_lexicon` and the Persian-accent
  declaration, hashes the prompt (FR-003/FR-004/FR-007).

**Engine / engine-package isolation (Principle V; audited by
tests/unit/asr/test_engine_import_isolation.py)** — each third-party engine
package is imported (function-local) in exactly one file:

- `whisper_mlx_engine.WhisperMLXEngine` — the ONLY file that `import mlx_whisper`.
  Lazy, memoised load via `ensure_loaded()`; VAD per-region transcription with
  word timings stitched back onto the original timeline.
- `vad.segment(wav_path) -> [SpeechRegion]` — the ONLY file that imports
  `silero_vad` / `onnxruntime`. Drops silence so pauses produce no phantom tokens
  (FR-006/SC-C); thresholds in `vad.vad_settings()` (research §b).
- `parakeet_engine.ParakeetEngine` — the ONLY file that `import parakeet_mlx`.

All engine-package imports are function-local so `speakloop --help` loads no
models (Principle VIII; guarded by tests/integration/test_help_without_models.py).

RNN-T/TDT (Parakeet) does NOT hallucinate on silence (research_asr.md), so the
VAD path runs only for Whisper.

**Dependency note (silero-vad ↔ torchaudio ↔ torchcodec):** `silero_vad.read_audio`
decodes audio via `torchaudio`. torchaudio≥2.11 moves decoding to `torchcodec`
(an unbundled dependency), which crashes on the first live VAD call. `pyproject`
pins `torchaudio<2.9` to keep the in-tree decode path. If you bump torchaudio,
run `uv run pytest -m live_asr` (real silero + real audio I/O) to confirm VAD
still loads a WAV before shipping.
