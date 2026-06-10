# Manual voice smoke test — US4 Trustworthy feedback pipeline (P4)

**Why manual:** real mishearings only arise from actual accented speech + the recognizer; the
deterministic hallucination filter and the consistency check are covered by automated tests
(`tests/unit/triage/`, `tests/integration/test_triage_guarantees.py`,
`tests/integration/test_artifact_consistency.py`). This checklist confirms the behavior on real audio.

## Commands

```bash
uv run speakloop practice --question activity-rotation-callbacks          # local
uv run speakloop practice --question activity-rotation-callbacks --cloud  # cloud coach + consistency
```

## Verify by ear / eye

- [ ] **Mispronounce a word** you mean (e.g. say "must" so it might transcribe as "mouse"). If it is
      mis-transcribed, it appears under **## Pronunciation flags** — NOT as a grammar error.
- [ ] **Silence/hallucination:** leave a long silent gap mid-answer. Any phantom phrase Whisper emits
      over the silence does NOT appear in the grammar feedback, the transcript, or the metrics.
- [ ] **Content error:** state a wrong fact (e.g. "Android 11" when the answer is "Android 12"). It
      appears under **## Content errors (vs. reference answer)**, separate from grammar.
- [ ] **Consistency (cloud):** run `--cloud`; the coaching section's facts match the reference answer.
      If the model invented a contradiction, the coaching section is corrected or omitted (never shows
      a wrong fact) — check the `coach_error` frontmatter note if it was withheld.

## Sign-off
- Tester: ____  Date: ____  Result: ☐ pass ☐ issues: ____
