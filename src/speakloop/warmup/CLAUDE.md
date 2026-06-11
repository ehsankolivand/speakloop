# warmup

## Purpose

The oral warm-up drill (010-interview-loop, P2c): generates 3 short target sentences
from the learner's top recurring grammar error and judges each spoken response
pass/fail/incomplete with immediate feedback. Generation uses the injected LLM;
judging is deterministic (no LLM).

## Public interface

- `drill.generate_drill(top_error_label, llm, *, system_prompt) -> list[DrillItem]`
  — calls `llm.generate` with `_DRILL_MAX_TOKENS=512`, `_DRILL_TEMPERATURE=0.4`
  (drill.py:21-22); generates `NUM_ITEMS=3` items (drill.py:23). Raises
  `LLMEngineError` on empty/failed response; coordinator skips warm-up gracefully.
- `drill.judge_item(item, response_text) -> DrillResult` — deterministic, offline.
  Result `"incomplete"` when `len(words) < _MIN_RESPONSE_WORDS=2` (drill.py:24,81).
  Result `"pass"` iff corrected form is present AND error form is absent in the
  lowercased word-token normalized response (drill.py:59-86). Empty `error_form`
  means `has_error` is always False — such items can only pass or be incomplete
  (accepted leniency by design, drill.py:85).
- `drill.load_drill_prompt() -> tuple[str, Path]` — seeds
  `~/.speakloop/openrouter_drill_prompt.txt` from the packaged default on first call;
  returns `(prompt_text, path)` (drill.py:39-45).
- `drill.DrillItem` — frozen dataclass: `target_sentence`, `corrected_form`,
  `error_form`.
- `drill.DrillResult = Literal["pass", "fail", "incomplete"]`.

## Dependencies & consumers

- Depends on: `speakloop.config` (paths), `speakloop.llm` (`LLMEngine`,
  `LLMEngineError`), `feedback.grammar_analyzer._extract_json` (shared JSON recovery).
  No engine package imported at module level (Principle V).
- Consumers: `sessions/coordinator.py` (runs warm-up before attempt 1, per-item
  budget `WARMUP_ITEM_BUDGET_SECONDS=20` at coordinator.py:538; 3 items × 20 s is
  the real mechanism behind the "30–60 s" claim); `cli/practice.py` (builds the
  drill runner over the shared engine).

## File map

- `drill.py` — tuning constants lines 21-24; `generate_drill`, `judge_item`,
  `load_drill_prompt`, `DrillItem`, `DrillResult`.
- `drill_prompt_default.txt` — packaged default; seeded to the editable user path.

## Invariants & traps

- `judge_item` is pure and deterministic — no LLM, no I/O, no side effects.
- Empty `error_form` always evaluates `has_error=False`; items with no error form
  cannot fail (only pass or incomplete).
- Generation is the only LLM step; failures degrade to skipped warm-up, never a
  crash. See degradation contract: `.claude/rules/llm-calls.md` (O8).
- Live audio (recording the drill response) is validated by the manual smoke test;
  no unit test covers it.

## Common modification patterns

- **Tune generation**: change `_DRILL_MAX_TOKENS`, `_DRILL_TEMPERATURE`, `NUM_ITEMS`,
  or `_MIN_RESPONSE_WORDS` at drill.py:21-24.
- **Change prompt**: edit `~/.speakloop/openrouter_drill_prompt.txt` (user-side) or
  the packaged `drill_prompt_default.txt` (repo-side default for new installs).
- **Change judging logic**: modify `judge_item` (drill.py:78-86); the word-token
  normalization regex is `_WORD_RE = re.compile(r"[A-Za-z0-9']+")`  (drill.py:27).

## Pointers

- Root map: `../../../CLAUDE.md`.
- LLM-call contract (C6): `.claude/rules/llm-calls.md`.
- schema_version rule: root CLAUDE.md (owner O3).
