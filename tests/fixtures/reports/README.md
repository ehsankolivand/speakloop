# Sample Session / report fixtures

Sample `Session` shapes (and, where useful, rendered report `.md` bodies) used by
the debrief **view-model** and **renderer** tests (`tests/unit/debrief/`).

## Contract

Fixtures here describe a fully-populated `speakloop.feedback.frontmatter.Session`
— attempts with metrics, ranked `grammar_patterns` carrying the additive fields
(`explanation`, `impact_rank`, per-evidence `corrected`), and the top-level
`cross_attempt_narrative` / `top_priority` — so the view model and renderer can
be exercised without running a live session.

Both Phase-B (no grammar patterns; `grammar_available=False` path) and Phase-C
(full grammar) shapes are represented so degradation rendering (FR-028) is
covered. The report file remains the only on-disk artifact in production; these
fixtures exist purely to drive deterministic UI tests.
