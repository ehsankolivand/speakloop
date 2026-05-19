# cli

Argument parsing + top-level dispatch via `typer`.

**Public surface**: `cli.main.app` (typer app).

- `practice` — listen/attempt loop.
- `doctor`  — health check.
- `trends`  — Phase C dashboard.

**Constraints**: `speakloop --help` MUST work with no models present (FR-018, SC-006).
No engine imports at module load time.
