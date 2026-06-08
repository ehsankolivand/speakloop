# cli

## Purpose

Argument parsing + top-level dispatch via `typer`. The user-facing entry point and the only
module that wires every other module together for a run.

## Public interface

- `main.app` — the `typer` app (exported from `__init__`). Commands:
  - `practice` — listen → session → debrief → menu loop. `--listen-only` skips the attempt
    phase; `--no-audio` skips reading the debrief aloud; `--asr-engine {whisper,parakeet}`
    picks the ASR engine (default `whisper`, falls back to Parakeet on load failure). The ASR
    engine is resolved once via `asr.build_engine(...)` and injected per session so a debrief
    **replay** re-enters the same question with no model reload (< 3 s). **`--cloud`** (008)
    routes ONLY the grammar feedback step to OpenRouter instead of the local Qwen model
    (`_build_cloud_grammar_analyzer`): resolve token (env > file; first-run prompt + privacy
    disclosure + store), preflight `check_auth()` (fail fast on a bad token), load the cloud
    prompt, build `OpenRouterEngine`. The local Qwen model is never validated/loaded in cloud
    mode. Default (no `--cloud`) is byte-for-byte unchanged + offline.
  - `doctor` — environment + model health check (`cli/doctor.py`); includes a "Cloud
    (OpenRouter)" section (model id, token present?, prompt path).
  - `trends` — Phase C dashboard.

## Dependencies

- Internal (orchestrates 9): `audio`, `config`, `content`, `feedback`, `installer`, `llm`,
  `sessions`, `trends`, `tts`; plus `debrief` imported function-local in `practice.py:290`.
- No engine packages imported at module load (so `--help` stays model-free).

## Consumers

The `speakloop` console script (entry point) — no internal module imports `cli`.

## File map

- `main.py` — the `typer` app + command registration.
- `practice.py` — the practice/debrief loop.
- `doctor.py` — health check.
- `trends.py` — dashboard command wiring.

## Common modification patterns

- **Add a command**: add a `@app.command(...)` in `main.py` delegating to a thin module here.
- **Add a `practice` flag**: edit `practice.py` (keep engine resolution injected, once).

## Traps

- `speakloop --help` MUST work with no models present — never import an engine package at module
  load time (Principle VIII; guarded by `tests/integration/test_help_without_models.py`).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md).
