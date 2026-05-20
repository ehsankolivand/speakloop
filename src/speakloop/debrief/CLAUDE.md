# debrief

Post-session interactive debrief — **render + audio + menu** (single
responsibility, Constitution Principle IV). Renders a finished `Session` in the
terminal, reads the educational parts aloud, and returns the user's next-step
choice (replay / new / quit).

**Public surface**:

- `DebriefChoice` — terminal menu selection (`replay` / `new` / `quit`).
- `run(session, *, sessions_dir, tts_engine, play_fn, no_audio=False) -> DebriefChoice`
  — the `DebriefRunner` contract (see
  `specs/002-post-session-debrief/contracts/debrief-interface.py`).

**Internal modules**: `view_model.py` (build `DebriefViewModel` from a
`Session`), `renderer.py` (`rich.Live` banner / cards / trend table /
transcripts + section highlight), `audio_player.py` (synth + sync + any-key
skip), `menu.py` (r/n/q + replay/new/quit + `t` transcript toggle), `debrief.py`
(orchestrator: announcement → audio+highlight → menu).

**Constraints**:

- **Principle V (engine isolation)**: this module MUST NOT import any
  engine-specific package — no `kokoro_mlx`, `mlx_audio`, `mlx_lm`,
  `parakeet_mlx`. TTS is used ONLY through the injected `TTSEngine` Protocol
  (`speakloop.tts`) plus an injected `play_fn` (`speakloop.audio.playback.play`).
- `cli/practice.py` is the only intended caller in v1.
- Never reads/writes the report file — the coordinator already wrote it; the
  debrief renders from the in-memory `Session` (data-model.md §C/§D).
- Transcripts and raw metrics are NEVER read aloud (FR-017) — only the
  narrative, top priority, and each pattern's explanation + corrected version.
- Must never hang: a TTS/playback failure still reaches the menu (FR-029); a
  no-control terminal falls back to plain `console.print` (research.md §c).
