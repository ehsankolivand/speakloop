# asr

## Purpose

Speech-to-text engine wrapper. Default engine **Whisper-large-v3-turbo** (mlx-whisper) with
per-session domain biasing + Silero-VAD pre-segmentation; Parakeet-TDT kept as
`--asr-engine parakeet` and as the automatic load-failure fallback (003-asr-l2-accent-accuracy).

## Public interface

- `interface.ASREngine` (Protocol) — `transcribe(wav_path, *, context=None) -> Transcript` and
  `ensure_loaded()`. The `context` keyword is additive/optional.
- `interface.Transcript`, `interface.WordTiming`, `interface.TranscriptionContext`,
  `interface.ASREngineError`.
- `selection.build_engine(name=None) -> EngineSelection` — resolves Whisper (default) or the
  requested engine, probes the load eagerly, falls back to Parakeet with one English reason on
  load failure. Imports wrapper classes only — no third-party engine package (Principle V).
- `domain_context.build_context(question) -> TranscriptionContext` — mines question + ideal
  answer + tags, adds the seed lexicon and a Persian-accent declaration, hashes the prompt.

## Dependencies

- **Engine packages owned here (Principle V — function-local, one file each):**
  `mlx_whisper` → `whisper_mlx_engine.py` (lines 78, 102, 118); `silero_vad` → `vad.py`
  (line 81); `parakeet_mlx` → `parakeet_engine.py` (line 48). `onnxruntime` is **transitive
  via `silero_vad`** — there is no `import onnxruntime` in this module (divergence D-1).
- Internal: `speakloop.installer` (model paths).

## Consumers

`feedback`, `metrics`, `sessions`.

## File map

- `interface.py` — Protocols + dataclasses (`Transcript`, `WordTiming`, `TranscriptionContext`).
- `selection.py` — `build_engine` resolution + Parakeet fallback.
- `whisper_mlx_engine.py` — the ONLY file that imports `mlx_whisper`; lazy memoised load; VAD
  per-region transcription with word timings stitched back onto the original timeline.
- `vad.py` — the ONLY file that imports `silero_vad`; `segment(wav) -> [SpeechRegion]`; drops
  silence so pauses produce no phantom tokens; thresholds in `vad_settings()`.
- `parakeet_engine.py` — the ONLY file that imports `parakeet_mlx`.
- `domain_context.py`, `seed_lexicon.py` — per-session biasing payload + term lexicon.

## Common modification patterns

- **Add an ASR engine**: implement the `ASREngine` Protocol in a new `*_engine.py`, keep its
  package import function-local, and wire it into `selection.build_engine`. Touch no other module.
- **Tune VAD**: edit `vad.vad_settings()` only.
- **Change biasing**: edit `domain_context.py` / `seed_lexicon.py`.

## Traps

- **`torchaudio<2.9` pin**: `silero_vad.read_audio` decodes via `torchaudio`; ≥2.11 moves
  decoding to the unbundled `torchcodec`, crashing the first live VAD call. `pyproject.toml:29`
  pins `torchaudio<2.9`. If you bump it, run `uv run pytest -m live_asr` before shipping.
- RNN-T/TDT (Parakeet) does not hallucinate on silence (research_asr.md), so the VAD path runs
  only for Whisper.

## Never do

- Import any engine package at module top level, or from more than one file (Principle V/VIII;
  audited by `tests/unit/asr/test_engine_import_isolation.py` and
  `tests/integration/test_help_without_models.py`).

## Pointers

- Root map: [`CLAUDE.md`](../../../CLAUDE.md); research: `doc/research_asr.md`,
  `doc/research_asr_l2_accent.md`.
