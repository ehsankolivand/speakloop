# cli

## Purpose

Argument parsing + top-level dispatch via `typer`. The only module that wires all other
modules together for a run; the console-script entry point.

## Public interface

Commands (all registered in `main.py`):
- `practice` (`main.py:63`) — listen → session → debrief loop. Key flags: `--listen-only`, `--no-audio`, `--asr-engine {whisper,parakeet}`, `--cloud` (alias for `--engine openrouter`), `--engine {local,openrouter,claude}`, `--speed` (TTS multiplier, default 0.85, clamped 0.5–2.0), `--timings`.
- `setup` (015, `main.py`) — pick + persist the feedback engine to `loop.yaml engine:` and download only what it needs. Flags: `--engine {local,openrouter,claude}`, `--no-download`. Thin module `setup.py`.
- `questions` (015) — typer sub-app: `validate [PATH]` / `template` / `where` (thin module `questions.py`).
- `doctor` (`main.py`) — environment + model health check, engine-aware (see below); `--json` for scripting.
- `trends` (`main.py:130`) — cross-session dashboard.
- `today` (`main.py:148`) — show due queue; `--limit`.
- `rebuild` (`main.py:160`) — rebuild derived store from session files; `--sessions-dir`.
- `resume` (`main.py:172`) — re-run analysis over analysis-pending transcripts; `--cloud`, `--engine`, `--timings`.

## Engine selection (practice.py + resume.py)

`resolve_engine_choice(engine, cloud) -> str` (`practice.py:265-289`): precedence is `--engine` flag → `loop.yaml engine:` → `"local"`. `--cloud` is an exact alias for `--engine openrouter`; combining `--cloud` with a non-openrouter `--engine` raises `EngineSelectionError(ValueError)`. `resume.py:86` imports and calls the same function.

`CLAUDE_TIER_MAP` (`practice.py:524-527`): `fast` → `("mishearing", "drill")`; `strong` → all remaining calls (grammar, coach, followups, keypoints, coverage, consistency). Fast tier defaults to `haiku`, strong to `sonnet` (`config/loop_config.py:23-24`).

`_build_runners(engine, *, fast_engine=None)` (`practice.py:530`) — builds the coordinator `Runners` bundle; for local/OpenRouter `fast_engine` is `None` (single instance, byte-identical); only the Claude Code builder passes a distinct fast engine.

**Engine-aware provisioning (015)**: `practice` ensures the required base phase (`"A"` listen-only / `"B"` full; decline → exit). Then, when `installer.engine_needs_local_llm(engine_choice, listen_only=...)`, it offers `ensure_models("C")` (the local Qwen) — declining/failing degrades to a recorded, resumable session (one notice, no exit); cloud engines never reach this. `setup.py` reuses the same predicate (base `"B"` always; `"C"` only for local). Default engine is set once via `speakloop setup` (`config.loop_config.save_engine`).

**`engine_status.py` (015)**: shared `active_engine()` + `engine_readiness(engine) -> EngineReadiness` (a `Requirement` list; cloud reqs `optional=True`). Used by `doctor` and `setup`; imports manifest/validator/credentials/`doctor_probe` function-locally (no engine package).

## doctor sections

`doctor.py` section groups: Feedback engine (015 — `_feedback_engine()`: active engine + `engine_status` readiness + next step; cloud/claude rows never FAIL), Models (`_models()` — **engine-aware (015)**: the Phase-C local LLM row FAILs on absence only when `active_engine()=="local"`, else "not required for the active engine"; TTS/ASR always FAIL on absence; all rows always rendered), aria2c, Cloud (OpenRouter), Interview Loop, Claude Code (`doctor_probe()`). Never FAILs exit code for Cloud or Claude Code rows (opt-in). Keep a `speakloop practice` substring on a FAIL model remediation (`test_missing_model_fails`).

## Output device warm-up

`playback.warm_output_device()` is called ONLY when `key_reader.raw_capable` is True (`practice.py:376-377`). Non-interactive runs (tests, piped input) skip it.

## Dependencies

- Internal (orchestrates all): `audio`, `asr`, `config`, `content`, `coverage`, `feedback`, `installer`, `interviewer`, `llm`, `sessions`, `srs`, `store`, `trends`, `triage`, `tts`, `warmup`. `debrief` is imported function-local at `practice.py:393`.
- No engine packages imported at module load (`speakloop --help` must work model-free; guarded by `tests/integration/test_help_without_models.py`).

## Consumers

The `speakloop` console script (entry point) — no internal module imports `cli`.

## File map

- `main.py` — `typer` app + command registrations (incl. `setup`, 015).
- `practice.py` — full practice/debrief loop; `resolve_engine_choice`, `EngineSelectionError`, `CLAUDE_TIER_MAP`, `_build_runners`; engine-aware provisioning (015, see above); `_cbreak_read` at line 118 (listen-loop raw reader — divergence note: `sessions/keyboard.py` is the session-path key reader, but the listen loop keeps its own `_cbreak_read`; code fix pending). `_listen_loop` prints the question text + a dim "Preparing audio…" line BEFORE synthesizing (a TTS cache miss pays the lazy Kokoro load there — don't reorder it back behind the synth calls).
- `setup.py` (015) — `run()`: resolve+persist engine, engine-aware download, readiness summary.
- `questions.py` (015) — `validate` / `template` / `where` over `content.load` + `content.template`; `template` prints to stdout via plain `print` (no rich markup parsing of the YAML), never writes a file.
- `engine_status.py` (015) — shared active-engine readiness (see above).
- `doctor.py` — health-check section groups (Feedback engine, Models [engine-aware], Cloud, Interview Loop, Claude Code).
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
- `_pick_question` re-prompts on invalid/out-of-range input; only Enter / q / quit / EOF cancels (returns None → caller prints "Bye." and exits). A typo must never exit the program.
- `_cbreak_read` in `practice.py:118` is separate from `sessions/keyboard.py`; do not remove it without also fixing the listen loop to use the `KeyReader` abstraction.

## Pointers

- Root map: `../../../CLAUDE.md`. LLM-caller rules: `.claude/rules/llm-calls.md`. Test rules: `.claude/rules/testing.md`.
