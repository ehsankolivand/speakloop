# Feature 009 — Implementation plan

## Approach

A **second** OpenRouter call ("coach") that runs after the existing grammar analyzer in cloud
mode and appends a free-form Markdown teaching section to the report. The two calls are
independent: the coach only *reads* the verified/grouped patterns produced by call 1; its output
is never fed back into the verify pipeline, so it cannot affect the grammar findings or the
verbatim guarantee. This mirrors feature 008's cloud-prompt pattern exactly (own packaged default
→ seeded user file → read verbatim).

## Architecture (why it's safe)

- **Reuse, don't fork.** The coach reuses the same `OpenRouterEngine` instance the grammar call
  used (same model from `openrouter.yaml`, same token). The engine's `generate(system_prompt,
  user_prompt, max_tokens, temperature)` is already the raw text interface — no JSON parsing — so
  free-form Markdown comes straight back.
- **Separation of concerns.** Coaching is its own module (`feedback/coach.py`) and its own prompt
  file. It never imports or references the grammar `_SYSTEM_PROMPT` or the grammar cloud prompt.
- **Body-only output.** The coaching Markdown is rendered into the report **body** (like the
  attempt transcripts), not serialized into frontmatter. Only the short `coach_error` diagnostic
  goes into frontmatter (additive optional, like `phase_c_error`).

## Code touchpoints

- `config/paths.py` — **+1** accessor `openrouter_coach_prompt_path()`
  (`~/.speakloop/openrouter_coach_prompt.txt`), mirroring `openrouter_prompt_path()`.
- `feedback/openrouter_coach_prompt_default.txt` — **NEW** packaged default coach prompt.
- `feedback/cloud_prompt.py` — **+1** loader `load_coach_prompt()` parallel to
  `load_cloud_prompt()` (seed-if-missing → read verbatim → return `(text, path)`).
- `feedback/coach.py` — **NEW** the only file building the coach prompt + making the coach call.
  `build_user_prompt(question, transcripts, patterns)` (excludes the ideal answer) and
  `coach(..., llm, system_prompt)` → Markdown; raises `LLMEngineError` on an empty response.
- `feedback/frontmatter.py` — **Session** gains `coaching` (body-only, not serialized) and
  `coach_error` (additive frontmatter key; dump + parse). `schema_version` stays 1.
- `feedback/report_builder.py` — **+1** `_coaching_section(session)`; `build()` appends it after
  the grammar section and before the transcripts (absent → byte-identical to the pre-009 layout).
- `sessions/coordinator.py` — `run_session(...)` gains a `coach=None` parameter; after a
  **successful** grammar analysis (`phase == "C"`) it runs the coach, capturing `coaching` /
  `coach_error` with graceful degradation. No-op when `coach is None` (local) or grammar degraded.
- `cli/practice.py` — `_build_cloud_grammar_analyzer` returns `(grammar_runner, coach_runner)`
  over one shared engine, prints the coach prompt path once, and `run()` passes `coach=` into
  `run_session`. The local `_build_grammar_analyzer` and the non-cloud branch are untouched (it
  returns `coach_runner = None`).
- `cli/doctor.py` — **+1** "coach prompt" row in the existing "Cloud (OpenRouter)" section.

`pyproject.toml` UNCHANGED (no new dependency — stdlib `urllib` transport, reused). Local Qwen
flow + `ensure_models(...)` untouched.

## Complexity tracking

Inherits 008's two opt-in deviations (network after model download; transcript text to a third
party) — both already justified for cloud mode. 009 adds **no new data category**: the coach call
sends the same transcripts + question + already-detected patterns to the same provider. The
reference/ideal answer is deliberately withheld from the coach.

## Test plan

- **Unit** `tests/unit/feedback/test_coach_prompt.py` — loader seeds-if-missing, reads verbatim,
  edit-changes-next-load, distinct asset from the grammar prompt + local `_SYSTEM_PROMPT`.
- **Unit** `tests/unit/feedback/test_coach.py` — user prompt carries question/attempts/patterns
  but **not** the ideal answer; success returns Markdown with `max_tokens=2048` and `retry=False`;
  empty response raises `LLMEngineError`.
- **Unit** `tests/unit/feedback/test_coaching_render.py` — coaching rendered verbatim between
  grammar and transcripts; absent → no coaching section.
- **Integration** `tests/integration/test_cloud_coaching.py` — coordinator: success appends the
  three sections in place; coach failure degrades gracefully (`coach_error` round-trips, grammar
  intact); coach skipped when grammar degraded; `coach=None` is a clean Phase-C report.
- **Integration** `tests/integration/test_cloud_mode.py` — updated for the `(grammar, coach)`
  return shape; new test that the coach runner routes the coach prompt over the same engine.
- Existing grammar / local-mode / report-invariance / frontmatter suites stay green.
