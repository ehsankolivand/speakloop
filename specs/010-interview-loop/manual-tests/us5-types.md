# Manual voice smoke test — US5 Question types (P5)

**Why manual:** confirms the behavioral/STAR and hypothetical question types end to end with real
speech. Schema parsing of `type` is covered by `tests/unit/content/test_type_field.py`; the report
sections by `tests/unit/feedback` rendering.

## Commands

```bash
uv run speakloop practice --question behavioral-anr-debugging      # STAR
uv run speakloop practice --question hypothetical-startup-anr      # conditionals
uv run speakloop practice --question activity-rotation-callbacks   # definition (unchanged)
```

## Verify by ear / eye

- [ ] **Behavioral:** the report includes a **## STAR structure check** marking which of
      Situation / Task / Action / Result you covered; the final-round goal is stated as
      "all STAR components within the time budget".
- [ ] **Hypothetical:** the report includes a **## Hypothetical — conditional & future forms**
      section; if you framed your answer with *if … I would …* it acknowledges it, otherwise it
      nudges you toward conditionals.
- [ ] **Definition** questions are unchanged — no STAR / conditional section appears.

## Sign-off
- Tester: ____  Date: ____  Result: ☐ pass ☐ issues: ____
