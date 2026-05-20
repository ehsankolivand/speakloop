# cli

Argument parsing + top-level dispatch via `typer`.

**Public surface**: `cli.main.app` (typer app).

- `practice` — listen → session → debrief → menu loop. `--listen-only` skips the
  attempt phase; `--no-audio` skips reading the debrief feedback aloud (visual
  only, FR-021). Engines (TTS/ASR) are constructed once before the loop and
  injected each session, so a debrief **replay** re-enters the same question with
  no model reload and no progress UI (< 3 s — FR-025/FR-026, SC-004).
- `doctor`  — health check.
- `trends`  — Phase C dashboard.

**Constraints**: `speakloop --help` MUST work with no models present (FR-018, SC-006).
No engine imports at module load time.
