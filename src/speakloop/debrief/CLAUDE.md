# debrief

## Purpose

Post-session interactive debrief — **render + audio + menu** (single responsibility). Renders a
finished `Session` in the terminal, reads the educational parts aloud, and returns the user's
next-step choice (replay / new / quit) [Phase C].

## Public interface

- `DebriefChoice` — terminal menu selection (`replay` / `new` / `quit`).
- `run(session, *, sessions_dir, tts_engine, play_fn, no_audio=False) -> DebriefChoice` — the
  `DebriefRunner` contract.

## Dependencies

- Internal: `speakloop.feedback` (the `Session` model), `speakloop.tts` (the `TTSEngine`
  Protocol only). TTS audio is consumed ONLY through the injected `tts_engine` + `play_fn`.
- **No engine package** is imported here (no `kokoro_mlx`/`mlx_lm`/`parakeet_mlx`) — Principle V.

## Consumers

`cli` — `cli/practice.py:290` imports it function-local; the only intended caller in v1.

## File map

- `view_model.py` — builds `DebriefViewModel` from a `Session`.
- `renderer.py` — `rich.Live` banner / cards / trend table / transcripts + section highlight.
- `audio_player.py` — synth + sync + any-key skip.
- `menu.py` — `DebriefChoice` + r/n/q + `t` transcript toggle.
- `debrief.py` — orchestrator: announcement → audio+highlight → menu.

## Common modification patterns

- **Change the menu**: edit `menu.py` (+ `DebriefChoice`).
- **Change what is read aloud**: edit `audio_player.py` — keep transcripts/raw metrics silent.

## Traps

- **Never read transcripts or raw metrics aloud** — only the narrative, top priority, and each
  pattern's explanation + corrected version (FR-017).
- **Must never hang**: a TTS/playback failure still reaches the menu; a no-control terminal
  falls back to plain `console.print`.

## Never do

- Import an engine package — TTS is injected via the `TTSEngine` Protocol + `play_fn` only.
- Read/write the report file — the coordinator already wrote it; debrief renders the in-memory `Session`.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contract: `specs/002-post-session-debrief/contracts/debrief-interface.py`.
