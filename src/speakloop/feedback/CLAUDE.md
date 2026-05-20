# feedback

Session-report assembly (Markdown + YAML frontmatter).

**Public surface**:

- `frontmatter.dump(session) -> str` — versioned schema, matches
  `contracts/report-frontmatter.yaml`. `schema_version` stays **1**; the debrief
  feature added the additive fields `GrammarPattern.explanation` /
  `.impact_rank` / `.catalog_id`, per-evidence `corrected`, and top-level
  `Session.cross_attempt_narrative` / `.top_priority` (all optional; unknown keys
  ignored for forward/back compat — data-model.md §A).
- `markdown_writer.write_atomic(path, content)` — temp-file + `os.replace`
  (FR-016, SC-005).
- `report_builder.build(session) -> str` — composes frontmatter + body; renders
  the "Top priority for next session" section, the cross-attempt narrative, and
  three-line `You said / Better / Because` fixes in `impact_rank` order, with the
  Phase-B placeholder and "no actionable patterns" fallbacks.
- `grammar_analyzer.analyze(transcripts, llm) -> list[GrammarPattern]` (Phase C)
  — catalog-aware: injects `detection_hints`, emits `corrected` + `explanation`,
  runs the coherence filter, keeps the verbatim-substring guarantee, suppresses
  no-op fixes (FR-009), and sorts by `impact_rank`.
- `catalog.get_catalog() -> Catalog` — the Persian-L1 transfer-error catalog
  (`persian_l1_catalog.yaml`); lookup by `id`/`label`, `OPEN_BUCKET_IMPACT_RANK`
  default (sorts below all catalog entries).
- `coherence.is_coherent(quote, transcripts)` / `coherence.make_filter(transcripts)`
  — deterministic ASR-garble filter (`common_words.txt`); runs AFTER the verbatim
  check, favours precision (attested transcript jargon is kept).
- `narrative.build_narrative(attempts, patterns)` /
  `narrative.select_top_priority(patterns, attempts)` — deterministic
  cross-attempt narrative + single most-impactful Top priority across grammar
  (`impact_rank`) and fluency (severity heuristic).
