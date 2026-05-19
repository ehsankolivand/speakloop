# trends

Cross-session progress dashboard (Phase C).

**Public surface**:

- `reader.read_reports(sessions_dir, since=None) -> list[Report]`.
- `aggregator.aggregate(reports, top_n) -> TrendsSummary`.
- `renderer.render(summary) -> rich.Console output`.

Reads Phase-B (interim) and Phase-C reports uniformly via `python-frontmatter`.
