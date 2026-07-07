# debrief

## Purpose

Post-session interactive debrief — render + audio + menu (single responsibility).
Renders a finished `Session` in the terminal, reads the educational parts aloud,
and returns the user's next-step choice (replay / new / quit) [Phase C].

## Public interface

- `DebriefChoice` — `str` enum: `REPLAY / NEW / QUIT` (`menu.py:23`).
- `run(session, *, sessions_dir, tts_engine=None, play_fn=None, no_audio=False, console=None, read_key=None) -> DebriefChoice`
  (`debrief.py:30-39`). Testability seams: `console` (inject a `Console`),
  `read_key` (inject a `Callable[[], str]` fake instead of real terminal reads).
- `ANNOUNCEMENT_LINE` (`debrief.py:68`) — exact string asserted by tests; do not
  change without updating those assertions.
- `DebriefViewModel` (`view_model.py:77`) — top-level view-model dataclass built
  from a `Session`; holds `audio_sections`, mutable `transcripts_expanded`. The
  inner dataclasses (`AttemptRow`, `PatternCard`, `TranscriptPreview`, `AudioSection`)
  are rediscoverable in `view_model.py`.
- `DebriefRenderer.print_static(*, highlight_ref, progress_text)` and `.live()`
  (`renderer.py:197-210`).

## Dependencies & consumers

- Internal: `speakloop.feedback` (`Session` model), `speakloop.tts` (`TTSEngine`
  Protocol, TYPE_CHECKING only — never a runtime engine import; Principle V).
- No engine packages (`kokoro_mlx` / `mlx_lm` / etc.) are imported — TTS is used
  exclusively through the injected `tts_engine` + `play_fn`.
- Consumer: `cli/practice.py:393` imports this module function-local (the only
  caller in production).

## File map

- `debrief.py` — orchestrator: view model → `print_static` → read aloud → menu;
  `ANNOUNCEMENT_LINE` constant. Read-aloud repaints the highlight IN PLACE via the renderer's
  `live()` (`rich.Live`) when `supports_live(console)` (a real terminal); non-terminals (test
  StringIO consoles) keep the per-section `print_static` fallback so captured output is stable
  (IMP-014 — previously it re-emitted the whole composed view per section and scrolled).
- `view_model.py` — `build_view_model(session, *, sessions_dir)` + all dataclasses.
- `renderer.py` — `DebriefRenderer`; `print_static` (one-shot) and `live` (`rich.Live`
  for animated highlight); `GRAMMAR_UNAVAILABLE_LINE`, `NO_PATTERNS_LINE`,
  `FIRST_TIME_LINE` constants.
- `audio_player.py` — `KeyboardSkip` context manager (background any-key skip via
  `select`/`termios`, `audio_player.py:37`); `read_aloud(sections, *, tts_engine,
  play_fn, on_section, skip_check) -> AudioOutcome`.
- `menu.py` — `DebriefChoice`, `run_menu(*, on_toggle, console, read_key, show_prompt)`;
  `read_key()` routes through the shared `sessions.keyboard.read_key_blocking` (3-byte read for
  arrow escapes) with its own `_decode_key`/`_parse_line` tables (IMP-016); handles `r/n/q` + `t`
  (transcript toggle, invokes `on_toggle`, keeps menu open) + `↑/↓` arrows + `Enter` (default REPLAY).

## Invariants & traps

- `debrief/menu.read_key` shares `sessions.keyboard.read_key_blocking` with the listen loop
  (IMP-016 — the previously-duplicated `_cbreak_read_key` cbreak ladder is gone). `menu.py`
  keeps only its own `_decode_key` (arrow escapes) + `_parse_line` token tables.
- `ANNOUNCEMENT_LINE` (`debrief.py:68`) is asserted verbatim by tests — do not rename
  or reword without updating those tests.
- TTS/playback failure MUST still reach the menu: errors are swallowed inside
  `audio_player.read_aloud` (FR-029); `no_audio=True` or `tts_engine=None` skips the
  read-aloud stage entirely.
- Never read transcripts or raw metrics aloud — only narrative, top priority, and each
  pattern's explanation + corrected version (FR-017).
- Never read/write the report file — the coordinator already wrote it; debrief renders
  the in-memory `Session`.
- `console` and `read_key` are the two testability injection seams — tests pass a
  fake `Console` and a pre-programmed key sequence; no real terminal needed.

## Common modification patterns

- **Change the menu options**: edit `menu.py` (+ `DebriefChoice`) and the `run_menu`
  dispatch table.
- **Change what is read aloud**: edit `view_model._audio_sections` — keep transcripts
  and raw metrics excluded.
- **Change the rendered layout**: edit `renderer.py`; keep constants in place if
  asserted by tests.

## Pointers

- Root map: `CLAUDE.md` (repo root).
- Testing rules: `.claude/rules/testing.md`.
- Contract: `specs/002-post-session-debrief/contracts/debrief-interface.py`.
