---
paths:
  - "src/speakloop/feedback/**"
  - "src/speakloop/coverage/**"
  - "src/speakloop/interviewer/**"
  - "src/speakloop/triage/**"
  - "src/speakloop/warmup/**"
---

# LLM-call rules (owner of rules O7 + O8 — specs/014-agent-context-overhaul/research.md)

## O7 — the `ideal_answer` boundary

`ideal_answer` must NEVER enter analytic LLM calls about the learner's speech.
Enforcement is structural — the excluded functions simply have no `ideal_answer`
parameter; keep it that way when changing signatures:

- Excluded: `feedback.grammar_analyzer.analyze` (grammar_analyzer.py:286),
  `feedback.coach.build_user_prompt` (coach.py:63-68 — "deliberately NOT passed in"),
  `feedback.narrative` / `feedback.coherence` (no ideal_answer anywhere),
  `interviewer.followups.generate_followups` (followups.py:47-53),
  `triage.mishearing.detect_mishearings` (mishearing.py:25).
- Legitimate exceptions (the ideal answer IS the reference there):
  `coverage.keypoints.derive_key_points` (keypoints.py:58-60),
  `coverage.scoring.score_coverage` (scoring.py:84),
  `triage.consistency.check_artifact` (defined consistency.py:34; ideal_answer enters the prompt at :42-44).

## O8 — degradation contract for every LLM caller

- All calls go through the injected `LLMEngine` Protocol (`llm/interface.py`) — never
  instantiate or import a concrete engine in a caller module.
- Failure → raise/propagate `LLMEngineError` → the coordinator/CLI degrades that ONE
  call (per-call `*_error` frontmatter key, e.g. `phase_c_error`, `coach_error`, or a
  skipped stage) — never crash the session, never auto-fall-back to another engine.
- JSON output recovery uses the shared ladder `feedback.json_recovery.extract_json`
  (json-repair based; details owned by `src/speakloop/feedback/CLAUDE.md`). Do not
  hand-roll repair regexes in a caller.
- Generation config (sampler, repetition penalty, stop tokens) is owned by the engine
  wrapper; callers pass only intent: `temperature`, `max_tokens`, `retry`.
