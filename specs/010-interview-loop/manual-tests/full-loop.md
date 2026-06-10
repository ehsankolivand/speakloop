# Consolidated manual smoke test — Interview Loop (010), entire loop

One end-to-end pass covering warm-up, attempts, follow-ups, coverage, content errors,
pronunciation flags, types, and the `today` / `practice` / `trends` / `rebuild` / `resume`
commands. Everything except live audio behavior is already covered by the automated suite
(`uv run pytest`); this checklist is the human gate for the spoken/interactive parts.

## Preconditions
- Working microphone + speakers (`uv run speakloop doctor` is green for Audio).
- Local Phase-C model installed, OR an OpenRouter token for `--cloud`.
- A few prior session reports exist (so trends + a top recurring error exist). If starting
  fresh, run a couple of plain sessions first, then `uv run speakloop rebuild`.

## Commands, in order

```bash
# 0. Health — confirm mic, models, store, prompts, loop config
uv run speakloop doctor

# 1. Build the cross-session store from existing reports
uv run speakloop rebuild

# 2. See what's due today (priority order; read-only)
uv run speakloop today

# 3. DEFINITION question — the full daily loop (local)
uv run speakloop practice --question activity-rotation-callbacks
#    cloud variant (adds the coach + consistency check):
# uv run speakloop practice --question activity-rotation-callbacks --cloud

# 4. BEHAVIORAL / STAR question
uv run speakloop practice --question behavioral-anr-debugging

# 5. HYPOTHETICAL question
uv run speakloop practice --question hypothetical-startup-anr

# 6. Trends dashboard (now includes per-pattern trend series)
uv run speakloop trends

# 7. Legacy flow still works (no warm-up / no follow-ups)
uv run speakloop practice --question activity-rotation-callbacks --no-warmup --no-followups

# 8. (If a session ever degrades) finish a pending one
uv run speakloop resume        # or: uv run speakloop resume --cloud

# 9. Read the latest report
ls -t data/sessions/*.md | head -1 | xargs less
```

## Verify by ear / eye

**Warm-up (step 3, when you have a recurring error)**
- [ ] 3 short sentences are spoken BEFORE attempt 1, targeting your top recurring error.
- [ ] Immediate ✓ / ✗ / … per item after each spoken response.
- [ ] With no prior errors, the warm-up is skipped cleanly.

**Attempts + final-round goal**
- [ ] The usual 4 / 3 / 2 timed attempts run.
- [ ] Before attempt 3 the tool states the goal: "cover all key points (or STAR components) within the time budget."

**Follow-ups**
- [ ] 1–2 spoken follow-ups after attempt 3, each grounded in your own words (not generic).
- [ ] **Latency:** first follow-up starts within ~10 s of attempt 3 ending (stopwatch; note if slower).
- [ ] **TTS pronunciation** of technical terms is intelligible: `onSaveInstanceState`, `ViewModelStore`, `ANR`, `API 28`.
- [ ] Answer one by voice → it's transcribed into the report's **## Follow-ups** section.
- [ ] Stay silent on the next → after ~60 s it records "_No answer — timed out._", loop continues, no crash.

**Coverage + content errors (P3)**
- [ ] Report shows **## Content coverage** with per-round covered/partial/missed and a first→final delta.
- [ ] State a wrong fact (e.g. "Android 11" vs "Android 12") → it appears under **## Content errors**, separate from grammar.

**Trustworthy pipeline (P4)**
- [ ] A long silence's phantom phrase never appears in grammar feedback / transcript / metrics.
- [ ] A mis-transcribed word appears under **## Pronunciation flags**, not as a grammar error.
- [ ] (cloud) The coaching section's facts match the reference answer (no invented exception names).

**Types (P5)**
- [ ] Behavioral report has **## STAR structure check** (which of S/T/A/R were present).
- [ ] Hypothetical report has **## Hypothetical — conditional & future forms** guidance.
- [ ] Definition report has neither (unchanged).

**Cross-session (P2)**
- [ ] `today` lists due questions sensibly; poorly-answered ones reappear within 1–2 days; "+N carried forward" when over capacity; "nothing due" only when all mastered.
- [ ] `trends` shows the per-pattern trend table (e.g. `10 → 4 → 1`), and grammar patterns in the report show a **Trend (recent sessions)** line.
- [ ] `rebuild` recreates `~/.speakloop/store.json` (delete it and re-run to confirm it's rebuildable).
- [ ] `resume` finishes any analysis-pending session (clears the flag, fills in grammar/coverage).

**Backward compatibility**
- [ ] Reports created before this feature still open cleanly in your editor / Obsidian.

## Reference
- Rendered example report (synthetic, behavioral): `tests/fixtures/reports/sample-full-loop.md`.

## Sign-off
- Tester: ____  Date: ____  Result: ☐ pass ☐ issues (list below):
