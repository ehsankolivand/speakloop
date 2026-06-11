# cli

## Purpose

Argument parsing + top-level dispatch via `typer`. The only module that wires all other
modules together for a run; the console-script entry point.

## Public interface

Commands (all registered in `main.py`):
- `practice` (`main.py:63`) — listen → session → debrief loop. Key flags: `--listen-only`, `--no-audio`, `--asr-engine {whisper,parakeet}`, `--cloud` (alias for `--engine openrouter`), `--engine {local,openrouter,claude}`, `--speed` (TTS multiplier, default 0.85, clamped 0.5–2.0), `--timings`.
- `doctor` (`main.py:120`) — environment + model health check; `--json` for scripting.
- `trends` (`main.py:130`) — cross-session dashboard.
- `today` (`main.py:148`) — show due queue; `--limit`.
- `rebuild` (`main.py:160`) — rebuild derived store from session files; `--sessions-dir`.
- `resume` (`main.py:172`) — re-run analysis over analysis-pending transcripts; `--cloud`, `--engine`, `--timings`.

## Engine selection (practice.py + resume.py)

`resolve_engine_choice(engine, cloud) -> str` (`practice.py:265-289`): precedence is `--engine` flag → `loop.yaml engine:` → `"local"`. `--cloud` is an exact alias for `--engine openrouter`; combining `--cloud` with a non-openrouter `--engine` raises `EngineSelectionError(ValueError)`. `resume.py:86` imports and calls the same function.

`CLAUDE_TIER_MAP` (`practice.py:524-527`): `fast` → `("mishearing", "drill")`; `strong` → all remaining calls (grammar, coach, followups, keypoints, coverage, consistency). Fast tier defaults to `haiku`, strong to `sonnet` (`config/loop_config.py:23-24`).

`_build_runners(engine, *, fast_engine=None)` (`practice.py:530`) — builds the coordinator `Runners` bundle; for local/OpenRouter `fast_engine` is `None` (single instance, byte-identical); only the Claude Code builder passes a distinct fast engine.

## doctor sections

`doctor.py` runs four section groups: Install (models, aria2c), Cloud (OpenRouter: model id, API token, system prompt, coach prompt — `doctor.py:117-164`), Interview Loop (store, loop config, five analysis prompts — `doctor.py:182-217`), Claude Code (binary, version, auth status via `doctor_probe()` — `doctor.py:220+`). Never FAILs exit code for Cloud or Claude Code rows (opt-in).

## Output device warm-up

`playback.warm_output_device()` is called ONLY when `key_reader.raw_capable` is True (`practice.py:376-377`). Non-interactive runs (tests, piped input) skip it.

## Dependencies

- Internal (orchestrates all): `audio`, `asr`, `config`, `content`, `coverage`, `feedback`, `installer`, `interviewer`, `llm`, `sessions`, `srs`, `store`, `trends`, `triage`, `tts`, `warmup`. `debrief` is imported function-local at `practice.py:393`.
- No engine packages imported at module load (`speakloop --help` must work model-free; guarded by `tests/integration/test_help_without_models.py`).

## Consumers

The `speakloop` console script (entry point) — no internal module imports `cli`.

## File map

- `main.py` — `typer` app + all six command registrations.
- `practice.py` — full practice/debrief loop; `resolve_engine_choice`, `EngineSelectionError`, `CLAUDE_TIER_MAP`, `_build_runners`; `_cbreak_read` at line 118 (listen-loop raw reader — divergence note: `sessions/keyboard.py` is the session-path key reader, but the listen loop keeps its own `_cbreak_read`; code fix pending).
- `doctor.py` — four health-check section groups (Cloud, Interview Loop, Claude Code).
- `trends.py` — `trends` command wiring.
- `today.py` — `today` command wiring.
- `rebuild.py` — `rebuild` command wiring.
- `resume.py` — `resume` command; reuses `resolve_engine_choice` from `practice.py:86`.
  The pending scan warns (yellow, with the parse error) and skips unreadable reports —
  never silently, so a corrupt pending report can't masquerade as "nothing to resume".

## Common modification patterns

- **Add a command**: add `@app.command(...)` in `main.py` delegating to a thin module file here.
- **Add a `practice` flag**: edit `practice.py`; keep engine resolution in `resolve_engine_choice`.
- **Add a doctor section**: add a `_<name>() -> list[CheckRow]` function in `doctor.py`, append its output in `run()`.

## Traps

- `speakloop --help` MUST work with no models present — never import engine packages at module load; guarded by `tests/integration/test_help_without_models.py`.
- `--cloud` + `--engine <non-openrouter>` raises `EngineSelectionError`; CLI prints it and exits 2.
- Mid-session Ctrl-C: `run()` catches `coordinator.AbortedError` around `run_session`, prints one yellow "Session aborted" line, and exits 130 (FR-016) — never a traceback. Follow-up-stage aborts don't raise (the coordinator writes a resumable report instead).
- `_cbreak_read` in `practice.py:118` is separate from `sessions/keyboard.py`; do not remove it without also fixing the listen loop to use the `KeyReader` abstraction.

## Pointers

- Root map: `../../../CLAUDE.md`. LLM-caller rules: `.claude/rules/llm-calls.md`. Test rules: `.claude/rules/testing.md`.
