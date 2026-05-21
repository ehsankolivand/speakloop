# trends

## Purpose

Cross-session progress dashboard [Phase C]. Reads past session reports and renders an aggregate
view of fluency/grammar trends. A leaf module — nothing else in `src/` depends on it.

## Public interface

- `reader.read_reports(sessions_dir, since=None) -> list[Report]`.
- `aggregator.aggregate(reports, top_n) -> TrendsSummary`.
- `renderer.render(summary) -> rich.Console output`.

## Dependencies

- Third-party: `python-frontmatter` (reads report YAML), `rich` (output). No internal module
  deps (leaf); no engine packages.

## Consumers

`cli` (the `trends` command).

## File map

- `reader.py` — loads Phase-B (interim) and Phase-C reports uniformly via `python-frontmatter`.
- `aggregator.py` — folds reports into a `TrendsSummary`.
- `renderer.py` — renders the dashboard with `rich`.

## Common modification patterns

- **Add a trend metric**: extend `aggregator.aggregate` + `renderer.render`.
- **Change which reports are read**: edit `reader.read_reports` (respects `schema_version` 1).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md).
