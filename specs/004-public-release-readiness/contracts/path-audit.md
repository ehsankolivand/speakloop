# Contract: Path-portability audit

A CI-only check (pytest) gating on machine-specific absolute paths in tracked content.
Logic lives in `tests/integration/test_path_portability_audit.py` (no shipped module).

## Detector

```python
def find_leaks(repo_root: Path) -> list[str]:
    """Return sorted 'path:line' strings for every machine-specific absolute-path
    leak in tracked, decodable text files. Empty list == clean tree."""
```

### Input
- Tracked files only: `git ls-files -z` run at `repo_root`.
- Each file read as UTF-8; undecodable (binary) files skipped.

### Flagged (machine-specific leak)
- POSIX home: regex `(/Users/|/home/)[A-Za-z0-9._-]+/`
- Windows home: regex `[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\`

### NOT flagged (portable — FR-009)
- `~/…` tilde-home references (e.g. `~/.speakloop/qa.yaml`).
- Angle-bracket placeholders: `/Users/<name>/`, `/home/<user>/`, `C:\Users\<name>\`
  (the captured segment contains `<` / `>`, which the `[A-Za-z0-9._-]+` class excludes).
- The audit module's own file (self-reference exclusion).

## Output
- **Pass**: `find_leaks(...)` returns `[]`; the test asserts emptiness.
- **Fail**: returns a non-empty list; the test fails and prints each `path:line` so the
  offending file is identified (FR-008).

## Test assertions
1. `find_leaks(repo_root) == []` on the current tree (FR-010, SC-B).
2. Positive self-test: a synthetic string with a concrete login (e.g. `/Users/`
   followed by a real-looking name and a slash) is detected (guards against a no-op
   gate, SC-B).
3. Negative self-test: `"~/.speakloop/qa.yaml"` and `"/Users/<name>/x"` are NOT detected
   (FR-009 — no false positives).
4. Wall-clock budget: `find_leaks(repo_root)` completes in < 2 s (FR-011, SC-G).

## Invariants
- Deterministic: files sorted; identical tree → identical result (FR-011).
- Stdlib + `git` only; no new dependency (FR-028).
- No network, reads local tree only (Principle II).
