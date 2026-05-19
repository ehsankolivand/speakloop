# feedback

Session-report assembly (Markdown + YAML frontmatter).

**Public surface**:

- `frontmatter.dump(session) -> str` — versioned schema, matches
  `contracts/report-frontmatter.yaml`.
- `markdown_writer.write_atomic(path, content)` — temp-file + `os.replace`
  (FR-016, SC-005).
- `report_builder.build(session) -> str` — composes frontmatter + body.
- `grammar_analyzer.analyze(transcripts, llm) -> list[GrammarPattern]` (Phase C).
