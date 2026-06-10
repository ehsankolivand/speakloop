# Manual voice smoke test — US1 Interactive Interviewer (P1)

**Why manual:** the follow-up stage is live audio (TTS playback + microphone recording +
latency). It cannot be validated automatically — the automated suite covers the non-audio wiring
(`tests/unit/interviewer/`, `tests/integration/test_followups_stage.py`) with stubs. This checklist
is the acceptance gate before starting P2.

**Preconditions**
- A working microphone and speakers/headphones (run `uv run speakloop doctor` first).
- The local Phase-C model installed (Qwen3-14B-4bit) — follow-ups need a language model. If you
  don't have it locally, run the cloud variant instead (`--cloud`, needs an OpenRouter token).
- Pick a question with enough substance to probe (e.g. `activity-rotation-callbacks`).

## Commands to run, in order

```bash
# 1. Environment health (mic, models, new store/prompt rows)
uv run speakloop doctor

# 2. Local run — full loop incl. the spoken follow-ups (answer each by voice)
uv run speakloop practice --question activity-rotation-callbacks

#    …or the cloud variant if you can't fit the local model:
# uv run speakloop practice --question activity-rotation-callbacks --cloud

# 3. Inspect the written report — confirm the new Follow-ups section is present
ls -t data/sessions/*.md | head -1 | xargs less    # or open the file in your editor

# 4. Legacy flow still works (no follow-ups) — regression check
uv run speakloop practice --question activity-rotation-callbacks --no-followups
```

## Verify by ear / eye

- [ ] **Follow-ups are spoken** after the 3rd timed attempt — 1 or 2 of them.
- [ ] **Grounded in your words:** each follow-up references something you actually said (or a gap
      you left) — it is NOT a generic/textbook question and NOT the original question reworded.
- [ ] **Latency:** the first follow-up starts playing within **~10 seconds** of attempt 3 ending.
      (Stopwatch it. If it's much slower, note the time — model-warming during attempt 3 is the
      known optimization to add; it is deliberately deferred until this measurement says it's needed.)
- [ ] **TTS pronunciation** of technical terms is intelligible — listen specifically for:
      `onSaveInstanceState`, `ViewModelStore`, `onRetainNonConfigurationInstance`, `ANR`, `API 28`.
      Note any term that is mangled.
- [ ] **Answer recording works:** speak an answer; it is captured and transcribed; the report's
      **## Follow-ups** section shows the question + your transcribed answer + any grammar feedback.
- [ ] **Silence → timeout:** on the next follow-up, say nothing. After ~60 s it times out, the loop
      continues, and the report shows that follow-up as **"_No answer — timed out._"** (no crash).
- [ ] **No regression:** `--no-followups` runs the classic single-question flow with no follow-up
      stage and writes a normal report.
- [ ] **Pronunciation flags (if any):** if the recognizer misheard a word you said, it appears under
      **## Pronunciation flags**, NOT as a grammar error.
- [ ] **Report opens cleanly** in your editor / Obsidian; older reports still open unchanged.

## Reference

A rendered example of the new report layout (built from synthetic data, for visual comparison):
`tests/fixtures/reports/sample-us1-followups.md`.

## Sign-off

- Tester: __________   Date: __________   Result: ☐ pass  ☐ issues (note below)
- Notes / latency measured / mispronounced terms:
