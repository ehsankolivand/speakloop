# store

## Purpose

Derived cross-session cache (010-interview-loop, P2a) — a single versioned JSON file
(`~/.speakloop/store.json`) holding: the SRS schedule, the key-point cache, and the
cross-session grammar-pattern occurrence series. **Never a source of truth**: fully
rebuildable from `data/sessions/*.md` via `speakloop rebuild`. Leaf — stdlib only,
no engine imports.

## Public interface

- `model.Store`, `model.ScheduleEntry`, `model.STORE_VERSION` — pure dataclasses;
  `Store.to_dict()` / `Store.from_dict()` round-trip the JSON.
- `io.load(path) -> Store` — returns empty `Store` on missing, corrupt, or
  newer-than-current `store_version` (caller rebuilds; io.py:20-33).
- `io.save_atomic(path, store)` — `tempfile.mkstemp` + `os.fsync` + `os.replace`
  (io.py:36-51); crash-safe, mirrors `feedback.markdown_writer.write_atomic`.
- `rebuild.rebuild(sessions_dir, *, rebuilt_at=None) -> Store` — folds every report
  into a fresh store: `patterns` (chronological occurrence series from
  `session.grammar_patterns` only — follow-up grammar patterns nested inside
  `follow_ups` entries are NOT folded, rebuild.py:52; divergence — code fix pending);
  `key_points` (latest set per question + ideal-answer hash); `schedule` (observed
  `last_grade`/`last_practiced`/`total_reviews`). `next_due` is set to the
  last-practiced date as a placeholder (rebuild.py:69) — `speakloop rebuild` does NOT
  restore the real SRS schedule. Schedule advance (interval ladder / next_due /
  mastery) happens at session end in `sessions/coordinator.py:1227` and
  `cli/resume.py:176`, not in rebuild.

## Dependencies & consumers

- Depends on: `speakloop.feedback` (`frontmatter.parse`). No `speakloop.srs` import
  anywhere in store/ — srs imports store, not the reverse.
- Consumers: `cli/rebuild.py` (`speakloop rebuild` command); `cli/resume.py:177-184`
  (loads store, advances schedule after resuming a session); `sessions/coordinator.py`
  (updates schedule after each practice session); `cli/today.py` / `cli/practice.py`
  (read the store for due-queue selection).

## File map

- `model.py` — `Store` / `ScheduleEntry` dataclasses + `STORE_VERSION`.
- `io.py` — `load` + `save_atomic` (fsync + os.replace).
- `rebuild.py` — fold session reports → `Store`.

## Invariants & traps

- The store is a **cache**: every field must be reconstructable from session files.
  Corruption is always recoverable via `speakloop rebuild`.
- `STORE_VERSION` is independent of the report `schema_version` (which stays 1;
  rule owned by root CLAUDE.md O3).
- `speakloop rebuild` sets `next_due` to `last_practiced` as a placeholder —
  **it does not restore real SRS intervals**. Users lose future scheduling fidelity
  on a rebuild; they recover it session by session as they practice.
- Main-thread store-write rule: see `src/speakloop/sessions/CLAUDE.md` (owner O6).

## Common modification patterns

- **Add a store section**: add a field to `Store` (`to_dict`/`from_dict`) and a
  fold step in `rebuild`; bump `STORE_VERSION` only on a breaking schema change.

## Pointers

- Root map: `../../../CLAUDE.md`.
- Contract: `specs/010-interview-loop/contracts/store-schema.md`.
- LLM degradation contract: `.claude/rules/llm-calls.md` (O8).
