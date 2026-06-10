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
    **replay** re-enters the same question with no model reload (< 3 s). **`--speed`** sets the
    Kokoro playback multiplier (default `0.85`, clamped to 0.5–2.0; lower = slower, for
    shadowing) and is fixed into the one injected `KokoroEngine` instance. **`--cloud`** (008)
    routes ONLY the grammar feedback step to OpenRouter instead of the local Qwen model
    (`_build_cloud_grammar_analyzer`): resolve token (env > file; first-run prompt + privacy
    disclosure + store), preflight `check_auth()` (fail fast on a bad token), load the cloud
    prompt, build `OpenRouterEngine`. The local Qwen model is never validated/loaded in cloud
    mode. Default (no `--cloud`) is byte-for-byte unchanged + offline. **009:**
    `_build_cloud_grammar_analyzer` now returns `(grammar_runner, coach_runner)` over ONE shared
    engine (also loads the coach prompt + prints its path once); `run()` passes `coach=` into
    `run_session` (the local branch passes `coach=None`). The coach is a SECOND cloud call run
    after a successful grammar analysis; its free-form Markdown is appended to the report.
    **012:** `practice`/`resume` gain `--timings` (print the per-stage breakdown; the
    `timings` frontmatter is saved regardless). `run()` builds ONE `KeyReader`
    (`sessions/keyboard.make_key_reader`) for the listen loop + session, reads
    `loop.yaml autoplay_ideal_answer` (skippable ideal answer) + `analysis_concurrency`,
    warms the output device, and passes the engine's declared `parallel_safe` into
    `run_session` (concurrent analysis for claude/openrouter; serial for local). The listen
    loop uses `playback.play_interruptible` so clips are skippable (`space`) / replayable (`r`).
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
