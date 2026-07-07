# interviewer

## Purpose

Interactive interviewer (010-interview-loop, P1). After the learner's final timed attempt,
generate 1–2 unscripted follow-up questions grounded SOLELY in the learner's own attempt
transcripts — never from the question bank (FR-001).

## Public interface

- `followups.generate_followups(question_text, transcripts, llm, *, system_prompt,
  max_count=2) -> list[dict]` — each spec is `{"question", "probe_ref", "probe_type"}`.
  Returns `[]` when combined real-speech transcript is below `MIN_PROBE_WORDS=30` (FR-006).
  Each kept follow-up passes `_is_grounded`: passes if any `>=4`-letter content word from the
  generated question appears in the learner transcript, OR `probe_ref` is non-empty
  (`followups.py:39-44`). Constants: `_FOLLOWUPS_TEMPERATURE=0.4`, `_FOLLOWUPS_MAX_TOKENS=256`.
  Routes JSON recovery through the shared `grammar_analyzer.generate_json` (one bounded
  regenerate on empty/parse-fail, IMP-011). Terminal failure still raises `LLMEngineError` on a
  still-empty response OR propagates `ValueError` on a still-unparseable one. The coordinator
  catches both with a broad `except Exception` — session never crashes.
- `prompts.load_followups_prompt() -> (text, path)` — seeds and reads
  `~/.speakloop/openrouter_followups_prompt.txt` (used in local AND cloud modes).

## Dependencies & consumers

- Internal: `speakloop.asr` (`Transcript`), `speakloop.config` (paths via `prompts.py`),
  `speakloop.llm` (`LLMEngine`). JSON recovery: shared `grammar_analyzer.generate_json` wrapper
  over the `_extract_json` ladder (see `src/speakloop/feedback/CLAUDE.md`).
- `ideal_answer` is EXCLUDED from `generate_followups` (followups.py:47-53); see
  `.claude/rules/llm-calls.md` O7.
- Consumers: `cli` (builds the follow-up runner over the shared engine),
  `sessions` (coordinator runs the follow-up stage with that runner).

## File map

- `followups.py` — probe-worthiness gate + generation + grounding check. Key constants at
  lines 24-29: `_FOLLOWUPS_MAX_TOKENS=256`, `_FOLLOWUPS_TEMPERATURE=0.4`, `MIN_PROBE_WORDS=30`,
  `MAX_FOLLOWUPS=2`.
- `followups_prompt_default.txt`, `prompts.py` — packaged default + seeding loader.

## Invariants & traps

- Follow-ups are derived ONLY from the three timed-attempt transcripts, never from follow-up
  answers (no recursion). The coordinator hard-slices to `specs[:2]` (`coordinator.py:456`).
- Follow-up answers ALSO pass hallucination triage before being recorded (`coordinator.py:509`).
- The `s`-key skip is handled by the coordinator (`_play_prompt` / `_record_stage`), not this
  module — this module only generates the question specs.
- 012 reorder: follow-up generation fires BEFORE heavy grammar/coverage analysis the instant
  the final transcript lands (`coordinator.py:1048-1069`), minimising the spoken-follow-up gap.
- `LLMEngineError` AND `ValueError` can escape `generate_followups`; always catch broadly when
  calling it.

## Common modification patterns

- **Change follow-up count cap**: edit `MAX_FOLLOWUPS` in `followups.py` AND `specs[:2]` slice
  in `coordinator.py:456`.
- **Adjust probe-worthiness threshold**: edit `MIN_PROBE_WORDS` in `followups.py`.

## Pointers

- Root CLAUDE.md: `../../../CLAUDE.md`. LLM degradation contract + `ideal_answer` boundary:
  `.claude/rules/llm-calls.md` (O7, O8). Contract: `specs/010-interview-loop/contracts/` (C1).
