# config

## Purpose

Single source of truth for filesystem paths and the daily-loop runtime config.
Two files with different stdlib footprints — see File map.

## Public interface

### paths.py (stdlib-only, no I/O beyond mkdir)

- `paths.models_dir()` — `~/.speakloop/models/`; env `SPEAKLOOP_MODELS_DIR` overrides.
- `paths.sessions_dir()` — `<cwd>/data/sessions/`; env `SPEAKLOOP_SESSIONS_DIR` overrides.
- `paths.tts_cache_dir()` — `~/.speakloop/cache/tts/`; env `SPEAKLOOP_TTS_CACHE_DIR`
  overrides (paths.py:128).
- `paths.default_qa_file()` — `<cwd>/content/questions.yaml` (repo default; pure, no exists check).
- `paths.qa_file_path()` — personal-override location (`--qa-file` / `SPEAKLOOP_QA_FILE` /
  `~/.speakloop/qa.yaml`).
- `paths.resolve_qa_file() -> Path | None` — active question file by precedence:
  `--qa-file` / `SPEAKLOOP_QA_FILE` → `~/.speakloop/qa.yaml` (if exists) →
  `content/questions.yaml` (if exists) → `None` (paths.py:103-124). **No auto-copy.**
- `paths.openrouter_token_path()` / `openrouter_config_path()` / `openrouter_prompt_path()`
  / `openrouter_coach_prompt_path()` — paths only; YAML read happens in `llm/`.
- `paths.store_path()` — `~/.speakloop/store.json` (010 cross-session store).
- `paths.loop_config_path()` — `~/.speakloop/loop.yaml` (010).
- `paths.logs_dir()` — `~/.speakloop/logs/` (017; opt-in debug logs only — written ONLY by
  `pronounce --debug`, never on a normal run; caller mkdir-s on demand).
- Five editable-prompt path functions (010): `openrouter_followups_prompt_path()`,
  `openrouter_keypoints_prompt_path()`, `openrouter_coverage_prompt_path()`,
  `openrouter_triage_prompt_path()`, `openrouter_drill_prompt_path()`.
- `paths.ensure_dir(path) -> Path` — mkdir -p, returns path.
- Env overrides: `SPEAKLOOP_HOME` (base home dir; default `~/.speakloop`);
  XDG-aware: `XDG_DATA_HOME`, `XDG_CACHE_HOME` used for fallback resolution.

### loop_config.py (imports pyyaml; reads ~/.speakloop/loop.yaml)

- `LoopConfig` frozen dataclass — all fields optional with silent defaults.
- `load() -> LoopConfig` — returns defaults on absent or malformed file (loop_config.py:58-65).
- `save_engine(engine) -> Path` (015) — the ONLY writer of `loop.yaml`. Validates against
  `VALID_ENGINES`, read-modify-writes (preserves other keys; pyyaml drops comments).
  **Refuses to overwrite** (raises `ValueError`) when an existing file isn't a YAML mapping —
  a typo or top-level list won't clobber the user's other keys. Called only by `speakloop
  setup` — no normal run auto-creates the file.

**loop.yaml key table** (all keys optional; parsed in `load()` at the cited lines):

| Key | Default | Validated | line |
|---|---|---|---|
| `daily_capacity` | 5 | max(1, int) | :66 |
| `engine` | `"local"` | must be in `VALID_ENGINES` = (local, openrouter, claude) | :71-73 |
| `claude_timeout_seconds` | 240 | max(1, int) | :75 |
| `analysis_concurrency` | 3 | max(1, int) | :79 |
| `autoplay_ideal_answer` | `True` | must be `bool` | :82-84 |
| `warmup_enabled` | `True` | bool() cast | :87 |
| `followups_enabled` | `True` | bool() cast | :88 |
| `claude_fast_model` | `"haiku"` | non-empty str | :90 |
| `claude_strong_model` | `"sonnet"` | non-empty str | :91 |
| `pronunciation_drills` (016) | `"auto"` | must be in (auto, on, off) | load() |
| `pronunciation_min_free_mb` (016) | 4500 | max(0, int) | load() |
| `pronunciation_tts_playback` (017) | `True` | must be `bool` | load() |
| `pronunciation_retries` (017) | 1 | int clamped to [0, 3] | load() |
| `pronunciation_tts_speed` (017 P2) | 0.85 | float clamped to [0.5, 1.5] | load() |

`loop_config.teach_speed(drill_speed) -> float` derives the slower per-sound teaching-beat speed
(a step below the drill speed, clamped to the floor) — used by both `cli` and `sessions`.

## Dependencies & consumers

- `paths.py`: stdlib only; no internal deps (leaf).
- `loop_config.py`: imports `pyyaml` + `speakloop.config.paths`.
- Consumers of config: `cli`, `coverage`, `feedback`, `installer`, `interviewer`,
  `llm`, `sessions`, `triage`, `tts`, `warmup`.

## File map

- `paths.py` — every path constant + `resolve_qa_file()` + `ensure_dir()`.
- `loop_config.py` — `LoopConfig` dataclass + `load()` (reads `~/.speakloop/loop.yaml`).

## Invariants & traps

- **Q&A precedence (O10)**: `--qa-file` / `SPEAKLOOP_QA_FILE` → `~/.speakloop/qa.yaml`
  (if exists) → `content/questions.yaml` (if exists) → `None`. The home file is an
  opt-in override — never auto-created (paths.py:103-124, specs/004-public-release-readiness).
- `paths.py` does no I/O except `ensure_dir()`; `loop_config.py` reads YAML at call time
  and writes ONLY via `save_engine()` (explicit `speakloop setup` action — never on a normal
  run, preserving the "nothing auto-created in your home dir" guarantee). Never add a network
  call or engine import to either file.

## Common modification patterns

- **Add a path or constant**: add a function in `paths.py`; never hard-code a path elsewhere.
- **Add a loop.yaml key**: add the field to `LoopConfig`, a default constant, and a
  parse branch in `load()` in the same commit.

## Pointers

- Root map: `CLAUDE.md`.
