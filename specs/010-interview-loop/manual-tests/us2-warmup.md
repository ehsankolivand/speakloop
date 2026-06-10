# Manual voice smoke test — US2 Cross-session memory / SRS / warm-up (P2)

**Why manual:** the warm-up drill is live audio (spoken target sentences + recorded responses).
The SRS math, queue, and trend rendering are covered by automated tests
(`tests/unit/srs/`, `tests/unit/trends/`); this checklist covers the spoken drill + the
`today` queue end to end.

**Preconditions:** at least 2–3 prior session reports on record (so a "top recurring error" and a
trend exist), the local Phase-C model (or `--cloud`), a working mic.

## Commands, in order

```bash
uv run speakloop rebuild        # build the derived store from your session files
uv run speakloop today          # show the due queue (priority order)
uv run speakloop practice       # session now OPENS with a 30–60s spoken warm-up
uv run speakloop trends         # dashboard now includes a per-pattern trend table
```

## Verify by ear / eye

- [ ] **Warm-up speaks 3 short sentences** targeting your top recurring error, BEFORE attempt 1.
- [ ] **Immediate pass/fail** per item: after each spoken response you see ✓ / ✗ / … (incomplete).
- [ ] **No-history case:** with no prior errors, the warm-up is skipped (no crash, goes to attempt 1).
- [ ] **`today`** lists due questions in sensible priority order; poorly-answered ones appear soon;
      shows "+N carried forward" when over capacity; says "nothing due" only if all mastered.
- [ ] **Report** now shows a **## Warm-up drill** section and **Trend (recent sessions)** lines on
      grammar patterns (e.g. `10 → 4 → 1`).
- [ ] **`trends`** shows the new per-pattern trend table.
- [ ] **`rebuild`** prints counts and recreates `~/.speakloop/store.json` (delete it and re-run to confirm).
- [ ] **`--no-warmup`** skips the warm-up.

## Sign-off
- Tester: ____  Date: ____  Result: ☐ pass ☐ issues: ____
