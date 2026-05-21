# Command matrix (T007; re-run T025, T044) — FR-003, FR-012, SC-I

Every command claimed in any `CLAUDE.md` plus the candidate build/test/lint set, run for real.

| Command | Status | Exit | Note |
|---------|--------|------|------|
| `uv run speakloop --help` | ✅ verified | 0 | Works with no models (Principle VIII). |
| `uv run speakloop doctor` | ✅ verified | 0 | `cli/doctor.py`, registered `cli/main.py:89`. Health check prints `[OK]` rows. Resolves the spec's "unconfirmed" assumption. |
| `uv run pytest` | ✅ verified | 0 | 306 passed, 3 skipped. Full suite green (SC-H). |
| `uv run pytest -m live_asr` | ✅ verified | 0 | Real silero+torchaudio smoke; marker `pyproject.toml:77`. Run when touching torchaudio. |
| `uv run pytest tests/integration/test_path_portability_audit.py` | ✅ verified | 0 | Path-portability gate (G6). |
| `uv run ruff check .` | ❌ FAILS | 1 | **19 pre-existing findings** (SIM105×7, UP042×4, SIM300×3, UP037×2, I001×2, F401×1) in committed code at HEAD `4c3c096`. NOT introduced by this feature; fixing requires code edits (FR-053 → flag-and-defer, divergence D-7). **NOT documented as a verified command.** |
| `uv run ruff format --check .` | ⚠ not clean | — | 26 files would be reformatted; same flag-and-defer class. Not documented as passing. |

**Documented in the rewritten top-level `CLAUDE.md` (verified-passing only):**
`uv run speakloop --help`, `uv run speakloop doctor`, `uv run pytest`,
`uv run pytest -m live_asr`, `uv run pytest tests/integration/test_path_portability_audit.py`.

**Lint:** `ruff` is the configured linter (`pyproject.toml [tool.ruff]`), but `ruff check .`
does not currently pass on committed code, so per FR-003 it is NOT presented as a "run this, it
passes" command. The conventions section names ruff as the linter and points to the D-7
deferral; no command that fails is documented. No documented command was found missing; no
real-but-undocumented passing command was found that needed adding.
