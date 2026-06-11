# asr

## Purpose

Speech-to-text engine wrapper. Default: Whisper-large-v3-turbo (mlx-whisper) with
per-session domain biasing + Silero-VAD pre-segmentation. Parakeet-TDT is the
`--asr-engine parakeet` option and the automatic load-failure fallback (003).

## Public interface

- `interface.ASREngine` (Protocol) — `transcribe(wav_path, *, context=None) -> Transcript`
  and `ensure_loaded()`.
- `interface.Transcript`, `interface.WordTiming`, `interface.TranscriptionContext`,
  `interface.SegmentMeta`, `interface.ASREngineError`.
- `selection.build_engine(name=None) -> EngineSelection` — resolves and eagerly loads the
  requested engine; falls back to Parakeet with an English `fallback_reason` on load failure.
  `EngineSelection` fields: `engine`, `engine_name`, `model_id`, `fell_back`,
  `fallback_reason` (`selection.py:27-34`).
- `domain_context.build_context(question) -> TranscriptionContext` — mines question + ideal
  answer + tags; adds seed lexicon and Persian-accent declaration; hashes the prompt.
- `vad.segment(wav_path) -> list[SpeechRegion]` — VAD pre-segmentation (Whisper path only;
  Parakeet does not hallucinate on silence so VAD is skipped there).
- `vad.vad_settings() -> dict` — the exact tunables that ran, recorded in frontmatter ASR
  provenance. Constants live in `vad.py` module scope: `SPEECH_THRESHOLD`, `MIN_SPEECH_MS`,
  `MIN_SILENCE_MS`, `MERGE_GAP_MS`, `SPEECH_PAD_MS` (`vad.py:30-35`).

## Engine packages owned here (Principle V — function-local, one file each)

- `mlx_whisper` → `whisper_mlx_engine.py` only (function-local; `_load`, `_load_audio`,
  `transcribe` — three import sites within that file).
- `silero_vad` → `vad.py` only (`vad.py:82`).
- `parakeet_mlx` → `parakeet_engine.py` only (`:48`).
- `onnxruntime` is transitive via `silero_vad` — no direct import in this module (D-1).

Audited by `tests/unit/asr/test_engine_import_isolation.py` and
`tests/integration/test_help_without_models.py`.

## Anti-hallucination guards

`whisper_mlx_engine.py:45-50`: `_DECODE_GUARDS` — temperature fallback tuple +
compression-ratio / logprob / no-speech thresholds passed explicitly to each `transcribe`
call to trigger Whisper's built-in retry on low-confidence decodes.
`whisper_mlx_engine.py:53`: `_is_degenerate(text)` — post-hoc safety net; detects
repetition loops via gzip compression ratio > 2.4.

`ensure_loaded()` is called during playback (pre-warm) so the first recording attempt
does not pay the model-load latency.

## Dependencies

- Internal: `speakloop.installer` (model paths). No other internal deps.

## Consumers

`cli`, `coverage`, `feedback`, `interviewer`, `metrics`, `sessions`, `triage`.

## File map

- `interface.py` — Protocols + dataclasses.
- `selection.py` — `build_engine` + `EngineSelection`; Parakeet fallback at `:57-73`.
- `whisper_mlx_engine.py` — sole `mlx_whisper` importer; VAD-region transcription with
  word timings stitched to the original timeline; `_DECODE_GUARDS` + `_is_degenerate` at
  `:45-67`.
- `vad.py` — sole `silero_vad` importer; `segment()` + `vad_settings()`; tuning constants
  at module scope; `silero_vad` import at `:82`.
- `parakeet_engine.py` — sole `parakeet_mlx` importer.
- `domain_context.py`, `seed_lexicon.py` — per-session biasing payload + term lexicon.

## Invariants & traps

- `torchaudio<2.9` cap: see root CLAUDE.md Traps (owner). One-line summary: `silero_vad`
  uses `torchaudio` for audio I/O; ≥2.11 routes through unbundled `torchcodec` and crashes
  the first live VAD call.
- Never import any engine package at module top level or from more than one file (Principle V).

## Common modification patterns

- **Add an ASR engine**: implement `ASREngine` Protocol in a new `*_engine.py`; keep its
  package import function-local; wire into `selection.build_engine`. Touch no other module.
- **Tune VAD**: edit module-scope constants in `vad.py`; `vad_settings()` picks them up.
- **Change biasing**: edit `domain_context.py` / `seed_lexicon.py`.

## Pointers

- Root map: `../../../CLAUDE.md` (torchaudio trap O2, engine-import rule O1).
- Research: `doc/research_asr.md`, `doc/research_asr_l2_accent.md`.
