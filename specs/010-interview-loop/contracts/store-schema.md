# Contract: Derived store (`~/.speakloop/store.json`)

A single versioned JSON file. **Internal cache, not a source of truth** — fully rebuildable from
`data/sessions/*.md` via `speakloop rebuild` (research R4). Written atomically (temp file + `os.replace`,
mirroring `markdown_writer.write_atomic`). stdlib `json` only.

## Shape

```json
{
  "store_version": 1,
  "rebuilt_at": "2026-06-10T09:00:00",
  "schedule": {
    "activity-rotation-callbacks": {
      "question_id": "activity-rotation-callbacks",
      "last_grade": "good",
      "interval_days": 4,
      "next_due": "2026-06-14",
      "consecutive_strong": 0,
      "mastered": false,
      "last_practiced": "2026-06-10",
      "total_reviews": 3
    }
  },
  "key_points": {
    "activity-rotation-callbacks": {
      "<sha256-of-normalized-ideal-answer>": {
        "question_id": "activity-rotation-callbacks",
        "ideal_answer_hash": "<sha256>",
        "key_points_version": 2,
        "question_type": "definition",
        "points": [ { "id": 1, "text": "rotation is a configuration change by default" } ]
      }
    }
  },
  "patterns": {
    "verb tense": [ ["2026-06-01", 10], ["2026-06-05", 4], ["2026-06-10", 1] ]
  }
}
```

## Invariants & operations

- **Rebuildable**: `store.rebuild(sessions_dir) -> Store` folds every report:
  - `schedule[q]` ← replay `answer_grade` + dates per question through `srs.schedule.next_due`
    (chronological); analysis-pending sessions leave the entry un-graded (still due).
  - `key_points[q][hash]` ← the `key_points` block recorded in the latest session for `q` (per hash).
  - `patterns[label]` ← occurrence counts per session date from each report's `grammar_patterns`
    (follow-up grammar tagged as such still counts, FR-036).
- **Recoverability**: a missing/corrupt/older-`store_version` file is rebuilt on next use; the rebuild is
  deterministic given the session files, so the store carries no information the files lack.
- **Atomic write**: never leaves a partially written store; `.tmp` removed on success.
- **No engine import**; pure stdlib. The store module is a leaf (depends only on `trends.reader`/
  `feedback.frontmatter` parsing + `srs`).

## CLI

`speakloop rebuild` → `store.rebuild(sessions_dir)` + `store.io.save_atomic` → prints counts
(questions scheduled, key-point sets, patterns). Exit 0 on success.
