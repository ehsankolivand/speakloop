# Contract: CLI commands

All commands are registered on the existing `typer` app (`cli/main.py`) with **lazy, function-local
engine imports** so `speakloop --help` loads no models (Principle VIII). New commands are thin wrappers
delegating to a `cli/` module (pattern: `practice_cmd`/`doctor_cmd`/`trends_cmd`).

## `speakloop practice` (MODIFY) — the daily loop

```
speakloop practice [QUESTION_ID] [--cloud] [--no-warmup] [--no-followups] [--qa-file PATH] [--no-audio]
```
- No `QUESTION_ID` → **due-question selection** from the SRS queue (FR-012/FR-034); a given `QUESTION_ID`
  practices that question on demand (preserved).
- Flow per session: **warm-up drill** (unless `--no-warmup` / no qualifying error) → listen → 3 attempts
  (4/3/2) → **1–2 follow-ups** (unless `--no-followups` / no probe material) → report.
- `--cloud` routes **all** new LLM steps + grammar + coach through OpenRouter (unchanged opt-in); default
  is local Qwen. `--no-warmup`/`--no-followups` restore the legacy single-question flow (FR-007a).
- Empty due queue (all mastered) → informs the learner, offers on-demand practice, no error (FR-017a).
- Exit 0; never crashes on analysis failure (writes deterministic report, sets `analysis_pending`).

## `speakloop today` (NEW) — the due queue

```
speakloop today [--limit N] [--qa-file PATH]
```
- Prints the due queue in **priority order** (most overdue → lower last grade → older last-practiced),
  capped at the daily capacity (default 5; `--limit` overrides); shows carry-forward count (FR-012/FR-015).
- Non-empty whenever any question is below mastery (FR-013); reads the store (rebuilds if missing).
- Read-only; loads no engines; exit 0.

## `speakloop trends` (MODIFY) — stats / dashboard

```
speakloop trends [--since DATE]
```
- Existing fluency + pattern-ranking dashboard, **plus** a per-pattern occurrence **trend series** across
  sessions (the FR-009 "stats" view). One command — no duplicate `stats` command (governance review).
- Read-only; loads no engines.

## `speakloop rebuild` (NEW) — rebuild the derived store

```
speakloop rebuild
```
- `store.rebuild(sessions_dir)` → `store.io.save_atomic`; prints counts (questions scheduled, key-point
  sets, patterns). Proves the store is fully rebuildable from session files (research R4). Loads no
  engines; exit 0.

## `speakloop resume` (NEW) — finish analysis-pending sessions

```
speakloop resume [--cloud]
```
- Finds reports with `analysis_pending: true`, re-runs the missing analysis (triage/grammar/coverage/
  follow-up analysis) over the **preserved transcripts**, rewrites the report (atomic), clears
  `analysis_pending`, and updates the store/schedule (FR-035a). Until resumed, the question stayed due
  and un-graded.
- `--cloud` selects the engine as in `practice`. Engines imported lazily; exit 0.

## `speakloop doctor` (MODIFY)

- Adds rows: derived-store presence/version + rebuildable check; presence of the new seeded prompt files
  (`~/.speakloop/openrouter_followups_prompt.txt`, `…_keypoints…`, `…_coverage…`, `…_triage…`, `…_drill…`);
  loop-config YAML. Exit 0 when healthy (unchanged contract).

## Invariants across all commands

- `speakloop --help` and every `<cmd> --help` work with **no models installed** (contract test
  `test_help_works_without_models`).
- Read-only commands (`today`, `trends`, `rebuild`) make **no** network calls and load **no** engines.
- New commands are English-only `rich` output; no GUI.
