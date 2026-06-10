# coverage

## Purpose

Content-coverage scoring (010-interview-loop, P3). Derives 5–7 key points from a
question's ideal answer (hash-versioned), scores each attempt covered/partial/missed
against them, and flags content errors (factual contradictions vs the ideal answer),
kept separate from grammar. The coverage aggregate drives the answer-quality grade.

## Public interface

- `keypoints.derive_key_points(question_text, ideal_answer, question_type, llm, *, system_prompt)
  -> list[{id, text}]` — 5–7 points (or the 4 STAR components for behavioral, P5).
- `keypoints.ideal_answer_hash(ideal_answer) -> str` — content version key (R3).
- `scoring.score_coverage(key_points, transcripts, ideal_answer, llm, *, system_prompt, version)
  -> CoverageResult` — ONE call over all attempts; returns per-attempt records
  (with the `(covered + 0.5·partial)/N` aggregate) + validated content errors +
  the final-round aggregate (drives the grade).
- `content_errors.validate_content_errors(raw) -> list[dict]` — keeps only
  mutually-exclusive contradictions (both claims present, distinct).

## Dependencies

- Internal: `speakloop.asr` (`Transcript`), `speakloop.llm` (`LLMEngine`/`LLMEngineError`),
  `feedback.grammar_analyzer._extract_json`. **No engine package imported** (Principle V).

## Consumers

`sessions` (the coordinator derives/caches key points + scores coverage),
`cli` (builds the keypoints/coverage runners over the shared engine).

## File map

- `keypoints.py` — derivation + content hashing + STAR components.
- `scoring.py` — the coverage call + per-attempt aggregate records.
- `content_errors.py` — content-error validation.
- `keypoints_prompt_default.txt`, `coverage_prompt_default.txt`, `prompts.py`.

## Traps

- The ideal answer IS passed to these calls (unlike grammar/coach) — it is the
  reference coverage is scored against. Key points are stored in the session report
  + the derived store, never written back into the question bank (R3).
- Coverage comparisons are valid only within one `key_points_version`; an ideal-
  answer edit bumps the hash → re-derivation → new version.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contracts: `specs/010-interview-loop/contracts/llm-calls.md` (C2, C3).
