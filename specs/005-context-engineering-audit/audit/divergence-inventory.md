# Divergence inventory (T011; appended through T027/T041/T051) — FR-001

Code is the source of truth. Severity: CRITICAL / MAJOR / MINOR / INFO.
Action `fix` = doc edit in this feature; `flag-and-defer` = needs code change, out of scope (FR-053).

| ID | Claim (doc `file:line`) | Ground truth (code `file:line`) | Severity | Action | Status |
|----|--------------------------|----------------------------------|----------|--------|--------|
| D-1 | `asr/CLAUDE.md:31` — `vad.py` is "the ONLY file that imports `silero_vad` / `onnxruntime`" | No direct `import onnxruntime` in `src/`; declared `pyproject.toml:30`, transitive via `silero_vad` | MINOR | fix wording in asr rewrite | ✅ fixed (T028) |
| D-2 | spec/old docs say "kokoro" | package is `kokoro_mlx` (`tts/kokoro_engine.py:41`, `pyproject.toml:18`) | MINOR | use `kokoro_mlx` in tech-stack + tts doc | ✅ fixed (T015, T030) |
| D-3 | isolation "audited by a test" (implied for all engines) | test exists for asr; `kokoro_mlx` isolation not asserted by any test | INFO | flag only (no test created, FR-053) | ⏸ deferred |
| D-4 | root map "Thirteen fine-grained modules" | 13 module dirs confirmed under `src/speakloop/` | INFO | accurate — keep | ✅ |
| D-5 | SPECKIT block listed 004 as active | active branch is `005-context-engineering-audit` | MINOR | update SPECKIT block | ✅ already 005 in working tree (T013) |
| D-6 | (none) `audio` → `sessions` upward import edge | `audio` imports `sessions.abort` | INFO | accurate — document in layout | ✅ noted (module-read-list) |
| D-7 | candidate `ruff check .` as a documented passing command | `ruff check .` exits 1 with 19 pre-existing findings at HEAD `4c3c096` | MINOR | flag-and-defer (code fix out of scope); NOT documented as verified | ⏸ deferred |

**Adversarial-review additions (T027):** none — sub-agent returned 0 CRITICAL / 0 MAJOR on the
first pass (see `adversarial-review-verdict.md`).

No CRITICAL or MAJOR divergence remains. D-3 and D-7 are deferral notes (code changes out of
scope); the docs are written to match current code in both cases.
