# tts

## Purpose

Text-to-speech engine wrapper (Kokoro-82M) plus a content-addressed clip cache.
Stable `TTSEngine` Protocol lets the engine be swapped by touching one file.

## Public interface

- `interface.TTSEngine` (Protocol): `synthesize(text, voice=None) -> Path`,
  `available_voices() -> list[str]`. The instance `speed` is the default; `KokoroEngine.synthesize`
  ALSO accepts an OPTIONAL per-call `speed=` override (017 P2 — backward-compatible superset of the
  Protocol; `None` ⇒ instance default). Kokoro's `save` takes per-call speed natively and the cache
  keys on the effective speed, so one engine renders several speeds (drill cadence + the slower
  teaching beat) with NO second model load and no cross-speed cache collision.
- `interface.TTSEngineError` — single error class for all TTS failures.
- `cache.cache_key(voice, text, speed=1.0) -> str` — sha256(voice|[speed|]text);
  speed folded into key only when ≠ 1.0 (cache.py:17-26).
- `cache.cache_path(voice, text, speed=1.0) -> Path`.
- `cache.lookup(voice, text, speed=1.0) -> Path | None` — on a hit, best-effort `os.utime` bumps
  the file's mtime so `prune`'s mtime-ordering is a true access-time LRU (IMP-038).
- `cache.store(voice, text, source_wav, speed=1.0) -> Path`.
- `cache.prune(max_bytes=TTS_CACHE_MAX_BYTES, *, keep=None) -> int` — LRU-evicts
  WAVs over 512 MB; never evicts `keep`; called at end of `synthesize` (kokoro_engine.py:101).
- `cache.purge() -> int` — deletes ALL cached WAVs; returns count (cache.py:90).
- `KokoroEngine(default_voice=DEFAULT_VOICE, speed=DEFAULT_SPEED)`.
  `DEFAULT_VOICE = "af_heart"`, `DEFAULT_SPEED = 1.0` (kokoro_engine.py:26-29).

## Dependencies & consumers

- **Engine package (function-local in kokoro_engine.py only):** `kokoro_mlx` imported
  inside `_load()` at kokoro_engine.py:52. This is the ONLY file in the repo that imports
  `kokoro_mlx` — guarded by `tests/unit/asr/test_engine_import_isolation.py` and
  `tests/integration/test_help_without_models.py`.
- Internal: `speakloop.config` (cache dir via `paths.tts_cache_dir()`),
  `speakloop.installer` (model path via `manifest.KOKORO_82M`).
- Consumers: `cli`, `debrief` (via injected `TTSEngine` Protocol).

## File map

- `interface.py` — `TTSEngine` Protocol + `TTSEngineError`.
- `kokoro_engine.py` — `KokoroEngine`; the only `import kokoro_mlx` (inside `_load()`).
- `cache.py` — content-addressed WAV store; `TTS_CACHE_MAX_BYTES = 512 MB`.

## Invariants & traps

- Cache location: `~/.speakloop/cache/tts/<sha256>.wav` by default;
  override via `SPEAKLOOP_TTS_CACHE_DIR` env (config/paths.py:128).
- `prune` is called after every `store`; it never evicts the clip just stored,
  so a freshly synthesised clip is always playable.
- `purge` deletes every `.wav` in the cache dir unconditionally — call only in tests
  or explicit user-initiated cleanup.

## Common modification patterns

- **Swap TTS engine**: implement `TTSEngine` in a new `*_engine.py`; keep the engine
  import function-local. Touch no other module.
- **Change cache keying or location**: edit `cache.py` only.
- **Change playback speed**: `KokoroEngine(speed=...)` for the instance default, or pass
  `synthesize(text, speed=...)` for a one-off (e.g. the trainer's slower teaching beat). Speed is
  encoded in the cache key when ≠ 1.0; existing default-speed entries stay hot.

## Pointers

- Root map: `CLAUDE.md`; engine research: `doc/research_tts.md`.
