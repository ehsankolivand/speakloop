# coverage

## Purpose

Content-coverage scoring (010-interview-loop, P3). Derives 5–7 key points from a
question's ideal answer (hash-versioned), scores each attempt covered/partial/missed
against them, and flags content errors (factual contradictions vs the ideal answer).
Coverage aggregate drives the answer-quality grade.

## Public interface

- `keypoints.derive_key_points(question_text, ideal_answer, question_type, llm, *, system_prompt)
  -> list[{id, text}]` — behavioral type returns the 4 STAR components without an LLM call;
  otherwise derives via LLM. Raises `LLMEngineError` on empty response.
- `keypoints.star_key_points() -> list[dict]` — the 4 STAR components (behavioral path).
- `keypoints.ideal_answer_hash(ideal_answer) -> str` — sha256[:16] of the normalized answer;
  the version key (R3).
- `scoring.score_coverage(key_points, transcripts, ideal_answer, llm, *, system_prompt, version)
  -> CoverageResult` — ONE LLM call over all attempts (`scoring.py:87`); returns
  per-attempt records + content errors + `final_aggregate`. Raises `LLMEngineError` on failure.
- `CoverageResult` dataclass: `attempt_records`, `content_errors`, `final_aggregate`.
- `content_errors.validate_content_errors(raw) -> list[dict]` — keeps only
  mutually-exclusive contradictions (both claims present, distinct).

## Dependencies & consumers

- Internal: `speakloop.asr` (`Transcript`), `speakloop.config` (paths via `prompts.py`),
  `speakloop.llm` (`LLMEngine`/`LLMEngineError`). JSON recovery: shared `_extract_json` ladder
  from `feedback.grammar_analyzer` (see `src/speakloop/feedback/CLAUDE.md`).
- `ideal_answer` is legitimately passed here (it is the reference); see `.claude/rules/llm-calls.md` O7.
- Consumers: `sessions` (coordinator derives/caches key points + scores coverage),
  `cli/resume.py:133-143` (re-scores coverage on pending-report retry).

## File map

- `keypoints.py` — derivation + hash + STAR components. `MIN_POINTS=5` (line 21) is a
  prompt-soft bound only — code caps at `MAX_POINTS=7` (defined line 22, enforced line 72); fewer than 5 is silently
  accepted if the model returns fewer.
- `scoring.py` — coverage call + per-attempt aggregate. Formula: `(covered + 0.5*partial)/N`
  rounded to 3 decimal places (`scoring.py:32-36`).
- `content_errors.py` — content-error validation.
- `keypoints_prompt_default.txt`, `coverage_prompt_default.txt`, `prompts.py` — prompts.

## Invariants & traps

- Coverage comparisons are valid only within one `key_points_version`; an ideal-answer edit
  bumps the hash → re-derivation → new version. Never compare aggregates across versions.
- Key points are stored in the session report + derived store; they are never written back
  into the question bank.
- `MIN_POINTS=5` is a prompt instruction, not a code guard — the code only enforces `MAX_POINTS=7`.
- Per-item `int()` on LLM-supplied fields (`ordinal`/`id` in `scoring._coverage_records`,
  `attempt_ordinal`/`key_point_id` in `content_errors.validate_content_errors`) is guarded:
  a non-numeric value skips just that attempt/coverage entry (scoring) or drops just that
  optional field (content_errors) — never raises, so one stray value can't discard the whole
  coverage pass and flag the report pending (IMP-005, mirrors `grammar_analyzer._verify_and_enrich`).

## Common modification patterns

- **Change the number of key points**: adjust `MIN_POINTS`/`MAX_POINTS` in `keypoints.py` AND
  the keypoints prompt.
- **Change aggregate formula**: edit `_aggregate` in `scoring.py:31-36`; re-run the equivalence suite.

## Pointers

- Root CLAUDE.md: `../../../CLAUDE.md`. LLM degradation contract + `ideal_answer` boundary:
  `.claude/rules/llm-calls.md` (O7, O8). Contracts: `specs/010-interview-loop/contracts/` (C2, C3).
