# tts

## Purpose

Text-to-speech engine wrapper (Kokoro-82M) plus a content-addressed clip cache. Sits behind a
stable interface so the TTS engine can be swapped in one file (Principle V).

## Public interface

- `interface.TTSEngine` (Protocol), `interface.TTSEngineError`.

## Dependencies

- **Engine package owned here (Principle V — function-local):** `kokoro_mlx` →
  `kokoro_engine.py` (line 41). This is the ONLY file in the repo that imports `kokoro_mlx`.
  (`mlx_audio` is named only in import-guard docstrings; it is never actually imported.)
- Internal: `speakloop.config` (cache dir), `speakloop.installer` (model path).

## Consumers

`cli`, `debrief` (the latter only through the injected `TTSEngine` Protocol).

## File map

- `interface.py` — `TTSEngine` Protocol + `TTSEngineError`.
- `kokoro_engine.py` — `KokoroEngine`; the only `import kokoro_mlx`.
- `cache.py` — content-addresses synthesised clips by `sha256(voice|text)` under
  `~/.speakloop/cache/tts/<key>.wav`.

## Common modification patterns

- **Swap TTS engine**: implement `TTSEngine` in a new `*_engine.py`, keep the package import
  function-local. Touch no other module.
- **Change cache keying/location**: edit `cache.py` only.

## Never do

- Import `kokoro_mlx` anywhere but `kokoro_engine.py`, or at module top level (Principle V/VIII).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md); research: `doc/research_tts.md`.
