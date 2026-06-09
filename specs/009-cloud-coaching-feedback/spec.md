# Feature 009 — Cloud coaching feedback

## Summary

Add a richer **coaching** layer to cloud-mode (`speakloop practice --cloud`) feedback so the
session report itself teaches the learner everything they need — a corrected version of their
own answer, focused teaching of their top habits, and paste-ready Anki cards — without ever
pasting the result into another tool.

This is **additive to cloud mode** and **cloud-only**. The existing strict grammar pipeline
(call 1) and local mode are untouched.

## Motivation

Cloud mode (008) routes only the strict `{"errors": [...]}` grammar extraction to OpenRouter.
That output is precise but terse: a list of ranked patterns with `You said / Better / Because`
lines. A motivated learner still has to assemble a clean answer, decide what to drill, and hand-
author flashcards elsewhere. The model the user already pays for can do all of that in one extra
call — turning the report into a self-contained study aid.

## User stories

- **US1** — After a cloud session, the report contains a clean, interview-ready rewrite of the
  learner's *own* answer (not a textbook answer), so they can read back what they were trying to
  say, said well.
- **US2** — The report names the 2–3 highest-impact habits to fix, with the rule, a corrected
  example from the learner's own words, and a self-check cue.
- **US3** — The report ends with 4–8 cloze-deletion Anki cards in one fenced code block, ready to
  paste into Anki's Cloze note type with no editing.
- **US4** — A learner can tune the coaching voice/format by editing one plain-text file
  (`~/.speakloop/openrouter_coach_prompt.txt`), with no code change.

## Functional requirements

- **FR-001** The coach is a **second** OpenRouter call that runs **after** the grammar analyzer,
  reusing the same `OpenRouterEngine` instance (same model, same token).
- **FR-002** The coach receives the **question**, the **three attempt transcripts**, and the
  **verified/grouped grammar patterns** from call 1 (label + each `quote → corrected`). It does
  **not** receive the reference/ideal answer (so it fixes the speaker's own words, never parrots
  the model answer).
- **FR-003** The coach output is **free-form Markdown**, never parsed by the grammar verify
  pipeline (V1–V3). It is appended to the report **after** the grammar/cross-attempt section and
  **before** the transcripts, verbatim (it already starts at level-2 headings).
- **FR-004** The coach runs **only in cloud mode** and **only after a successful grammar
  analysis**. If grammar degraded to `phase_c_error`, coaching is skipped too.
- **FR-005** Output token budget is generous (`max_tokens = 2048`) to fit the corrected answer +
  teaching + cards.
- **FR-006** **Graceful degradation**: if the coach call raises any `LLMEngineError` (transient
  API failure, timeout, empty response), the coaching sections are skipped entirely, the rest of
  the report is left intact, and a short non-fatal `coach_error` note is recorded in frontmatter.
  Never crash, never block the grammar report.
- **FR-007** The coach system prompt lives in its **own** packaged default
  (`feedback/openrouter_coach_prompt_default.txt`), seeded on first use to
  `~/.speakloop/openrouter_coach_prompt.txt`, then read verbatim — wholly separate from the
  grammar cloud prompt and the local `_SYSTEM_PROMPT`.

## Out of scope / non-goals

- Any change to call 1 (its prompt, its `{"errors": [...]}` schema, the V1–V3 verify path, or its
  rendering) — these stay byte-identical.
- Any change to local mode (`qwen_engine.py`, the local `_SYSTEM_PROMPT`, the non-cloud build
  path). Local sessions get no coaching section.
- Report `schema_version` (stays **1**; `coach_error` is an additive optional key, `coaching` is
  body-only and never serialized to frontmatter).
- New abstractions / provider frameworks / config knobs beyond the one editable prompt file.

## Success criteria

- **SC-001** A successful cloud session report contains `## Your answer, improved`,
  `## What to focus on`, and `## Anki cards`, placed between the grammar section and the
  transcripts.
- **SC-002** A coach failure yields a report that still contains the grammar section and no
  coaching sections, with a `coach_error` note in frontmatter that round-trips through `parse`.
- **SC-003** The default (non-cloud) path is byte-for-byte unchanged and offline; `schema_version`
  stays 1.

## Privacy

Same opt-in disclosure as 008: cloud mode sends attempt transcripts to OpenRouter. The coach call
sends the **same** transcripts (plus the question and the already-detected patterns) to the
**same** provider — no new data category leaves the device, and audio + reports stay local. The
reference/ideal answer is deliberately excluded.
