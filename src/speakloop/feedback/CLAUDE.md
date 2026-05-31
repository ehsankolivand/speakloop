# feedback

## Purpose

Session-report assembly: Markdown body + versioned YAML frontmatter, plus the educational
grammar/coherence analysis that feeds the report. The "what the user reads after a session" layer.

## Public interface

- `frontmatter.dump(session) -> str` — versioned schema (`schema_version` stays **1**); all
  002/003/006 additions are additive optional keys (e.g. top-level `asr:`, `ideal_answer:`);
  unknown keys ignored. Exports the `OPEN_BUCKET_IMPACT_RANK = 99` fallback constant for
  legacy-report parse paths.
- `markdown_writer.write_atomic(path, content)` — temp-file + `os.replace` (crash-safe write).
- `report_builder.build(session) -> str` — composes frontmatter + body (optional "Question &
  reference answer" copy of the Q&A `ideal_answer` when present, Top-priority section,
  cross-attempt narrative, `You said / Better / Because` fixes in `impact_rank` order, with
  Phase-B and "no actionable patterns" fallbacks).
- `grammar_analyzer.analyze(transcripts, llm) -> list[GrammarPattern]` [Phase C] — **free-form
  prompt**: the model returns its own `error_type` strings which become `GrammarPattern.label`
  verbatim. Grouped by `error_type`, verbatim-substring guaranteed on `quote`,
  coherence-filtered, no-op-fix-suppressed, sorted by `(-occurrence_count, label)` with
  `impact_rank` assigned 1..N. No catalog.
- `coherence` / `narrative` — deterministic ASR-garble filter + cross-attempt narrative + top
  priority selection.

## Dependencies

- Internal: `speakloop.asr` (`Transcript`), `speakloop.config` (paths), `speakloop.llm`
  (`LLMEngine`, used only by `grammar_analyzer`). No engine packages imported directly.
- Third-party: `python-frontmatter`, `pyyaml`, `json-repair` (grammar JSON recovery).

## Consumers

`cli`, `debrief`, `sessions`.

## File map

- `frontmatter.py` — `Session` model + schema (`schema_version` 1; additive keys preserved;
  `OPEN_BUCKET_IMPACT_RANK` constant for legacy parse fallback).
- `markdown_writer.py` — atomic write.
- `report_builder.py` — report composition.
- `grammar_analyzer.py` — free-form LLM grammar analysis (the only file here touching
  `speakloop.llm`). Recovery ladder: `json.loads` → first-`{...}` strict → `json_repair`
  (recovers single quotes, trailing commas, junk tokens, AND truncation) → one bounded
  regenerate on parse-fail/loop (`retry=True`) → graceful `phase_c_error` fallback.
  Grouping by `error_type` does dedupe naturally. Calls the LLM with `temperature=0.3`.
- `coherence.py`, `narrative.py` — garble filter, narrative + top priority selection.

## Common modification patterns

- **Add a frontmatter field**: add it optional in `frontmatter.py`; never bump `schema_version`.
- **Tune grammar analysis**: edit `grammar_analyzer.py` (keep the verbatim guarantee).
  JSON recovery is `json-repair`, not hand-rolled regex — don't reintroduce the old repair
  regexes. Generation config (sampler/rep-penalty/stop) is owned by `llm/qwen_engine.py`;
  pass intent (`retry`) and `temperature` only.

## Traps

- **`schema_version` stays 1** — every new key is additive and optional; a bump would break
  trends/back-compat.
- **`GrammarPattern.catalog_id` field is retained** as an additive optional for legacy-report
  round-trip; new sessions always set it to `None` (no catalog).
- **`Session.ideal_answer` is human-only** (post-2026-05-25): copied verbatim from the Q&A
  file and rendered as the "## Question & reference answer" body section + a frontmatter
  `ideal_answer:` block scalar. **Never** pass this field into `grammar_analyzer.analyze()`,
  `narrative.build_narrative()`, or any LLM call — they take transcripts/metrics only. It is
  a reference for the reader, NOT a feedback dimension (see 006 contract I7).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contract: `specs/002-post-session-debrief/contracts/report-frontmatter.yaml`.
