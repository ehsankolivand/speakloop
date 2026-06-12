# feedback

## Purpose

Session-report assembly: versioned YAML frontmatter + Markdown body, plus free-form
LLM grammar analysis, cloud coaching, timing instrumentation, and atomic file write.
"What the user reads after a session."

## Public interface

- `frontmatter.dump(session) -> str` / `frontmatter.parse(text) -> Session` — YAML
  frontmatter serializer. `SCHEMA_VERSION = 1` (`frontmatter.py:11`). All new keys are
  additive optional; unknown keys are ignored on parse. Exports `OPEN_BUCKET_IMPACT_RANK
  = 99` for legacy-report parse fallback.
- `markdown_writer.write_atomic(path, content)` — temp file + `os.fsync` + `os.replace`
  (crash-safe; `markdown_writer.py:10-29`).
- `markdown_writer.next_available_path(base_dir, date_str, question_id) -> Path` —
  primary name `YYYY-MM-DD-<question_id>.md`; collision suffix `-2`, `-3`, …
  (`markdown_writer.py:35-50`).
- `report_builder.build(session) -> str` — order: header → cross-attempt comparison →
  grammar section → coaching section (009, cloud only, body-only) → interview-loop
  sections (010) → pronunciation-drills section (016) → transcripts. The 016 section
  (`_pronunciation_drills_section`) delegates wording to `pronunciation.render_drills_section`
  (function-local import; pure formatter, no engine package) and is None when no drills ran →
  a no-drills report is byte-identical.
- `grammar_analyzer.analyze(transcripts, llm, *, max_tokens, system_prompt=None) ->
  list[GrammarPattern]` — see **Owner O4** block below. Calls LLM with `temperature=0.3`.
- `coach.coach(question_text, transcripts, patterns, llm, *, system_prompt) -> str`
  [009, cloud only] — second cloud call; free-form Markdown teaching + Anki cards;
  `ideal_answer` deliberately NOT passed in (`coach.py:63-68`). Raises `LLMEngineError`
  on failure; coordinator degrades → `coach_error` frontmatter key.
- `timings.StageTimer` [012] — injectable clock; `start/stop(overlapped=True)`, `record()`
  APIs; `to_frontmatter(*, analysis_mode, analysis_concurrency, analysis_wall_seconds)
  -> dict` (`timings.py:69-88`); `render() -> rich.Table`. Always-on; `--timings` flag
  gates display only.
- `cloud_prompt.load_cloud_prompt()`, `load_coach_prompt()` — seed `~/.speakloop/` from
  packaged defaults on first use; return `(text, path)`.

## Owner O4 — JSON recovery ladder

`grammar_analyzer._extract_json` (`grammar_analyzer.py:99-137`):

1. `_strip_code_fences` pre-step (`grammar_analyzer.py:89-96`).
2. `json.loads` strict on stripped text.
3. `json.loads` strict on first `{...}` region (tolerates surrounding prose).
4. `json_repair.loads` on full text.
5. `json_repair.loads` on `{...}` region only.

Raises `ValueError` only when all four rungs fail. Independently,
`_looks_like_repetition_loop` (`grammar_analyzer.py:140-159`) triggers ONE bounded
regenerate (`retry=True`) on parse failure OR detected loop — these two paths are
separate. On terminal failure → raises `LLMEngineError` → coordinator records
`phase_c_error`; session never crashes.

**013 note:** `openrouter_prompt_default.txt` output-format block hardened by commit
`b611f8d` to enforce JSON discipline from the cloud model.

Never hand-roll repair regexes. `json-repair` handles truncated/unclosed objects.

`SPEAKLOOP_DEBUG_LLM=1` dumps raw LLM output (first 8000 chars) to
`data/sessions/.debug-llm-raw/` (`grammar_analyzer.py:162-180`).

## Dependencies & consumers

- Internal: `speakloop.asr` (`Transcript`), `speakloop.config` (paths),
  `speakloop.llm` (`LLMEngine` — grammar_analyzer only). No engine packages directly.
- Third-party: `python-frontmatter`, `pyyaml`, `json-repair`.
- Consumers: `cli`, `debrief`, `sessions`.

## File map

- `frontmatter.py` — `Session`, `GrammarPattern`, `AsrProvenance`, `AttemptMetrics`,
  `Attempt` dataclasses + `dump`/`parse`. `Session.coaching` body-only (not serialized
  to frontmatter; `frontmatter.py:108-118`). `Session.timings` additive optional.
- `markdown_writer.py` — `write_atomic` + `next_available_path`.
- `report_builder.py` — body composition; coaching inserted after grammar, before
  interview-loop sections + transcripts.
- `grammar_analyzer.py` — the ONLY file touching `speakloop.llm` here. Free-form
  prompt: model's own `error_type` strings → `GrammarPattern.label`. V1 verbatim
  substring, V2 coherence filter, V3 no-op-fix suppression; sort `(-occurrence_count,
  label)`; `impact_rank` 1..N.
- `cloud_prompt.py` — `load_cloud_prompt()` / `load_coach_prompt()`.
- `coach.py` — `build_user_prompt` + `coach(...)`. Cloud-only.
- `coherence.py`, `narrative.py` — ASR-garble filter + cross-attempt narrative.
- `timings.py` — `StageTimer`. Inner block has its own `TIMINGS_SCHEMA = 1`; report
  `schema_version` stays 1.
- `openrouter_prompt_default.txt`, `openrouter_coach_prompt_default.txt` — packaged
  default prompts.

## Invariants & traps

- **`schema_version` stays 1** — additive optional keys only; pointer to root CLAUDE.md.
  016 adds `Session.pronunciation_drills: dict | None` (the drill-block result) — DISTINCT
  from the 010 `pronunciation_flags` (ASR mishearings). Emitted only when present.
- **`GrammarPattern.catalog_id`** retained for legacy round-trip; new sessions → `None`.
- **`ideal_answer` never enters analytic LLM calls** — see `.claude/rules/llm-calls.md`.
- Generation config (sampler, rep-penalty, stop tokens) owned by `llm/qwen_engine.py`;
  `grammar_analyzer` passes `temperature`, `max_tokens`, `retry` only — see
  `src/speakloop/llm/CLAUDE.md`.

## Common modification patterns

- Add a frontmatter field: add optional in `frontmatter.py`; never bump `schema_version`.
- Tune grammar analysis: edit `grammar_analyzer.py`; keep verbatim guarantee and
  4-rung ladder; pass only `temperature`/`max_tokens`/`retry` to the engine.
- Add a timings stage: call `timer.start/stop` or `with timer.stage(...)`.

## Pointers

- Root map: `../../../CLAUDE.md`
- LLM-call rules (ideal_answer boundary + degradation): `.claude/rules/llm-calls.md`
- Frontmatter contract: `specs/002-post-session-debrief/contracts/report-frontmatter.yaml`
