# feedback

## Purpose

Session-report assembly: Markdown body + versioned YAML frontmatter, plus the educational
grammar/coherence analysis that feeds the report. The "what the user reads after a session" layer.

## Public interface

- `frontmatter.dump(session) -> str` — versioned schema (`schema_version` stays **1**); all
  002/003 additions are additive optional keys (e.g. top-level `asr:`); unknown keys ignored.
- `markdown_writer.write_atomic(path, content)` — temp-file + `os.replace` (crash-safe write).
- `report_builder.build(session) -> str` — composes frontmatter + body (Top-priority section,
  cross-attempt narrative, `You said / Better / Because` fixes in `impact_rank` order, with
  Phase-B and "no actionable patterns" fallbacks).
- `grammar_analyzer.analyze(transcripts, llm) -> list[GrammarPattern]` [Phase C] — catalog-aware,
  coherence-filtered, verbatim-substring guaranteed, sorted by `impact_rank`.
- `catalog.get_catalog() -> Catalog` — the Persian-L1 transfer-error catalog.
- `coherence` / `narrative` — deterministic ASR-garble filter + cross-attempt narrative + top
  priority selection.

## Dependencies

- Internal: `speakloop.asr` (`Transcript`), `speakloop.config` (paths), `speakloop.llm`
  (`LLMEngine`, used only by `grammar_analyzer`). No engine packages imported directly.
- Third-party: `python-frontmatter`, `pyyaml`, `json-repair` (grammar JSON recovery, 006).

## Consumers

`cli`, `debrief`, `sessions`.

## File map

- `frontmatter.py` — `Session` model + schema (`schema_version` 1; additive keys at 20/40/91).
- `markdown_writer.py` — atomic write.
- `report_builder.py` — report composition.
- `grammar_analyzer.py` — LLM grammar analysis (the only file here touching `speakloop.llm`).
  Recovery ladder (006): `json.loads` → first-`{...}` strict → `json_repair` (recovers single
  quotes, trailing commas, junk tokens, AND truncation) → one bounded regenerate on
  parse-fail/loop (`retry=True`) → graceful `phase_c_error` fallback. Dedupe merges same-label
  patterns before ranking. KEEPS V1–V5 (verbatim, coherence, no-op drop, open-bucket gate, sort).
- `catalog.py`, `coherence.py`, `narrative.py` — Persian-L1 catalog, garble filter, narrative.

## Common modification patterns

- **Add a frontmatter field**: add it optional in `frontmatter.py`; never bump `schema_version`.
- **Tune grammar analysis**: edit `grammar_analyzer.py` / `catalog.py` (keep the verbatim guarantee).
  JSON recovery is `json-repair`, not hand-rolled regex — don't reintroduce the old repair regexes.
  Generation config (temp/rep-penalty/stop) is owned by `llm/qwen_engine.py`; pass intent (`retry`), not config.

## Traps

- **`schema_version` stays 1** — every new key is additive and optional (lines 20, 40, 91); a
  bump would break trends/back-compat (specs 002/003).

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contract: `specs/002-post-session-debrief/contracts/report-frontmatter.yaml`.
