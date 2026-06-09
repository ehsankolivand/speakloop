# config

## Purpose

Single source of truth for filesystem paths and runtime constants. A leaf module — pure path
resolution, no I/O beyond `mkdir -p`.

## Public interface

- `paths.models_dir()` → `~/.speakloop/models/` (or `--models-dir` override).
- `paths.sessions_dir()` → `data/sessions/` (CWD-relative; overridable).
- `paths.default_qa_file()` → `content/questions.yaml` (CWD-relative in-repo default).
- `paths.qa_file_path()` → the personal-override location (`--qa-file` / `SPEAKLOOP_QA_FILE` /
  `~/.speakloop/qa.yaml`).
- `paths.resolve_qa_file()` → active question file by precedence (`--qa-file` →
  `~/.speakloop/qa.yaml` if present → `content/questions.yaml` if present → `None`).
- `paths.tts_cache_dir()` → `~/.speakloop/cache/tts/`.
- `paths.openrouter_token_path()` / `openrouter_config_path()` / `openrouter_prompt_path()`
  (008) → `~/.speakloop/openrouter_token` · `openrouter.yaml` · `openrouter_prompt.txt`;
  `openrouter_coach_prompt_path()` (009) → `~/.speakloop/openrouter_coach_prompt.txt`.
  **PATHS ONLY** — the YAML is *read* in `llm/openrouter_config.py` (via `pyyaml`), so this
  leaf stays stdlib-only and does no I/O.

## Dependencies

- Standard library only. No internal module deps (leaf); no engine packages.

## Consumers

`cli`, `feedback`, `installer`, `sessions`, `tts`.

## File map

- `paths.py` — every path/constant + `resolve_qa_file()`.

## Common modification patterns

- **Add a path/constant**: add a function in `paths.py`; never hard-code a path elsewhere.

## Traps

- **Q&A precedence is `--qa-file → ~/.speakloop/qa.yaml → content/questions.yaml`, no
  auto-copy.** The home file is an opt-in override, not created for you (`resolve_qa_file`,
  `specs/004-public-release-readiness/`).

## Never do

- Import an engine package, or do I/O beyond `mkdir -p`.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md).
