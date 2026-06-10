# warmup

## Purpose

The 30–60 s oral warm-up drill (010-interview-loop, P2c). Generates 3 short target
sentences from the learner's top recurring error and judges each spoken response
pass/fail/incomplete with IMMEDIATE feedback. Generation uses the injected LLM;
judging is deterministic (no LLM).

## Public interface

- `drill.generate_drill(top_error_label, llm, *, system_prompt) -> list[DrillItem]`
  — 3 items via the injected `LLMEngine` + shared JSON recovery; raises
  `LLMEngineError` on empty/failed response (coordinator then skips the warm-up).
- `drill.judge_item(item, response_text) -> DrillResult` — deterministic: `pass`
  iff the corrected form is present and the error form absent; `incomplete` on an
  empty/garbage/silent response (not a fail); else `fail`.
- `drill.DrillItem`, `drill.DrillResult`, `drill.load_drill_prompt()` (seeds
  `~/.speakloop/openrouter_drill_prompt.txt`).

## Dependencies

- Internal: `speakloop.config` (paths), `speakloop.llm` (`LLMEngine`/`LLMEngineError`),
  `feedback.grammar_analyzer._extract_json`. **No engine package imported** (Principle V).

## Consumers

`sessions` (the coordinator runs the warm-up before attempt 1), `cli` (builds the
drill runner over the shared engine).

## File map

- `drill.py` — generation + deterministic judge + prompt loader.
- `drill_prompt_default.txt` — packaged default drill prompt.

## Traps

- Judging is deterministic and offline; generation is the only LLM step. Live audio
  (speaking the drill, recording the response) is validated by the manual smoke test.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contract: `specs/010-interview-loop/contracts/llm-calls.md` (C6).
