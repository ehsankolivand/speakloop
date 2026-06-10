# interviewer

## Purpose

Interactive interviewer (010-interview-loop, P1). After the learner's final timed
attempt, generate 1–2 **unscripted** follow-up questions grounded SOLELY in the
learner's own attempt transcripts (a gap, an edge case, or a "why") — never from
the question bank (FR-001). The coordinator speaks each follow-up, records the
voice answer, and runs it through the same per-attempt analysis.

## Public interface

- `followups.generate_followups(question_text, transcripts, llm, *, system_prompt,
  max_count=2) -> list[dict]` — returns `{"question", "probe_ref", "probe_type"}`
  specs; `[]` when the combined real-speech transcript is below the probe-worthiness
  threshold (`MIN_PROBE_WORDS = 30`, FR-006). Each kept follow-up is checked to be
  grounded in the learner's own words (a shared content word or a stated probe
  reference, SC-010). Raises `LLMEngineError` on empty/transient failure.
- `prompts.load_followups_prompt() -> (text, path)` — seeds and reads
  `~/.speakloop/openrouter_followups_prompt.txt` (used in local AND cloud modes).

## Dependencies

- Internal: `speakloop.asr` (`Transcript`), `speakloop.config` (paths),
  `speakloop.llm` (`LLMEngine`/`LLMEngineError`), `feedback.grammar_analyzer._extract_json`
  (shared JSON recovery ladder).
- **No engine package imported** (Principle V); the call uses the injected engine.

## Consumers

`cli` (builds the follow-up runner over the shared engine), `sessions`
(the coordinator runs the follow-up stage with that runner).

## File map

- `followups.py` — probe-worthiness gate + generation + grounding check.
- `followups_prompt_default.txt`, `prompts.py` — packaged default + seeding loader.

## Traps

- Follow-ups are derived ONLY from the three timed-attempt transcripts, never from
  earlier follow-up answers (no recursion); the coordinator asks at most 2.
- Live behavior (TTS pronunciation, ~10s latency, silence timeout) is validated by
  the manual voice smoke test — it cannot be exercised automatically.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contract: `specs/010-interview-loop/contracts/llm-calls.md` (C1).
