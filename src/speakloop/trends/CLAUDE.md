# trends

## Purpose

Cross-session progress dashboard [Phase C]. Reads past session reports and renders an
aggregate view of fluency and grammar trends. A leaf module — nothing in `src/` depends
on it (aggregator/renderer have intra-module imports only).

## Public interface

- `reader.read_reports(sessions_dir, *, since=None) -> ReadResult` (`reader.py:46-87`)
  — flat `sessions_dir.glob("*.md")`, non-recursive (`reader.py:58`). Returns
  `ReadResult(reports: list[Report], skipped: list[tuple[Path, str]])`. Non-speakloop
  `.md` files (missing `schema_version`/`attempts`/`generated_by_phase`) are silently
  skipped; malformed speakloop files are recorded in `.skipped` with a reason string
  (`reader.py:42-43`, `reader.py:61-62`).
- `reader.iter_reports(result) -> Iterator[Report]` — convenience wrapper.
- `aggregator.aggregate(reports, *, top_n=10) -> TrendsSummary` — folds reports into
  summary. `TrendsSummary` fields: `total_sessions`, `date_range`, `metric_series`,
  `pattern_ranking`, `pattern_series` (010 P2a: `dict[str, list[tuple[date, int]]]`,
  `aggregator.py:37`).
- `aggregator.format_series(series, *, window=3) -> str` — last `window` counts as
  `"10 → 4 → 1"` (`aggregator.py:40`; the renderer overrides with `window=5`, `renderer.py:76`).
- `renderer.render(summary, *, console=None) -> str` (`renderer.py:13`) — returns
  captured plain-text output (uses an internal `StringIO` Console when `console` is
  `None`). Four tables: (1) totals + date range, (2) fluency metrics attempt-3
  trajectory, (3) top-N grammar pattern ranking, (4) per-pattern trend table
  (`renderer.py:67-77`).

## Named constants

- `aggregator.METRIC_KEYS` — 5-metric tuple (single source for ORDERING): `speech_rate_wpm`,
  `filler_density_per_100_words`, `pauses_count`, `mean_pause_ms`, `self_corrections_count`.
- `aggregator.METRIC_LABELS` (key → human label) + `METRIC_HIGHER_IS_BETTER` (key → bool) —
  display metadata (IMP-042): the renderer shows the label, and `_delta_cell` annotates the Δ
  `(better)`/`(worse)` per direction (WPM up good; fillers/pauses/self-corrections up = worse).

## Dependencies & consumers

- Third-party: `python-frontmatter`, `rich`. No other speakloop-module imports.
- Consumers: `cli` (the `trends` command).

## File map

- `reader.py` — `Report` + `ReadResult` dataclasses; `read_reports`; `iter_reports`.
  Loads Phase-B and Phase-C reports uniformly via `python-frontmatter`.
- `aggregator.py` — `TrendsSummary`, `PatternRankRow` dataclasses; `aggregate`;
  `format_series`. Imports `reader.Report` only (intra-module).
- `renderer.py` — `render`. Imports `aggregator.TrendsSummary` + `format_series`
  (intra-module).

## Invariants & traps

- `read_reports` returns `ReadResult`, not `list[Report]`; callers must use
  `.reports` or `iter_reports`.
- `renderer.render` returns a `str` (captured output), not `None` or a Console object;
  pass `console=` to redirect to an existing Console.
- Frontmatter keys are additive optional — old Phase-B reports without `grammar_patterns`
  parse fine (empty list default).

## Common modification patterns

- Add a trend metric: extend `METRIC_KEYS` + add a `METRIC_LABELS`/`METRIC_HIGHER_IS_BETTER`
  entry in `aggregator.py`; the renderer picks up the label + direction automatically.
- Add a per-pattern series: extend `TrendsSummary.pattern_series` population in
  `aggregate`; render in the 4th table in `renderer.render`.

## Pointers

- Root map: `../../../CLAUDE.md`
- Testing rules: `.claude/rules/testing.md`
