# store

## Purpose

The derived cross-session **store** (010-interview-loop, P2a) — a single versioned
JSON file (`~/.speakloop/store.json`) holding the SRS schedule, the key-point cache,
and the cross-session grammar-pattern occurrence series. It is an **internal cache,
never a source of truth**: fully rebuildable from `data/sessions/*.md` via
`speakloop rebuild`. A leaf module — stdlib only, no engine imports.

## Public interface

- `model.Store`, `model.ScheduleEntry`, `model.STORE_VERSION` — pure dataclasses;
  `Store.to_dict()` / `Store.from_dict()` round-trip the JSON object.
- `io.load(path) -> Store` — returns an empty `Store` if the file is missing,
  corrupt, or a newer `store_version` (so the caller rebuilds).
- `io.save_atomic(path, store)` — temp file + `os.replace` (crash-safe), like
  `feedback.markdown_writer.write_atomic`.
- `rebuild.rebuild(sessions_dir, *, rebuilt_at=None) -> Store` — folds every report
  into a fresh store: `patterns` (chronological occurrence series), `key_points`
  (latest set per question + ideal-answer hash). **Schedule replay** records the
  observed grade history now; the interval-ladder / next-due / mastery computation
  is owned by `srs.schedule` and wired in by P2 (see the rebuild docstring).

## Dependencies

- Internal: `speakloop.feedback` (`frontmatter.parse`). In P2 it also uses
  `speakloop.srs` for schedule replay.
- stdlib only otherwise (`json`, `os`, `tempfile`, `dataclasses`); **no engine packages.**

## Consumers

`cli` (the `rebuild` command, and — from P2 — `today`/`practice` read the store),
`sessions` (the coordinator updates the schedule after each report, from P2).

## File map

- `model.py` — `Store` / `ScheduleEntry` dataclasses + `store_version`.
- `io.py` — JSON load + atomic save.
- `rebuild.py` — fold session reports → `Store`.

## Common modification patterns

- **Add a store section**: add a field to `Store` (+ `to_dict`/`from_dict`) and a
  fold in `rebuild`; bump `STORE_VERSION` only on a breaking change (older files
  then load as empty and rebuild).

## Traps

- The store is a **cache**: never put data here that cannot be reconstructed from
  session files. Corruption is always recoverable via `speakloop rebuild`.
- `STORE_VERSION` is independent of the report `schema_version` (which stays 1).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contract: `specs/010-interview-loop/contracts/store-schema.md`.
