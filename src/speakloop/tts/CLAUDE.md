# tts

Text-to-speech engine wrapper.

**Public surface**: `interface.TTSEngine` (Protocol), `interface.TTSEngineError`.

**Engine wrapper**: `kokoro_engine.KokoroEngine` — the ONLY file in the repo allowed
to `import kokoro_mlx` / `import mlx_audio` (Constitution Principle V).

**Cache**: `cache.py` content-addresses synthesised clips by `sha256(voice|text)`
under `~/.speakloop/cache/tts/` (FR-004).
