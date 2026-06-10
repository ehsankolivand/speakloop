# Quickstart: Interview Loop

How the daily training loop runs once this feature lands. Everything is the existing CLI — no new
dependency, no GUI. Local by default (offline); add `--cloud` to route the analysis to OpenRouter.

## The daily loop (one command)

```bash
# 1. See what's due today (priority order; read-only, no models loaded)
uv run speakloop today

# 2. Run the loop — due-question selection → warm-up → question + 4/3/2 attempts → follow-ups → report
uv run speakloop practice            # local Qwen (offline)
uv run speakloop practice --cloud    # route analysis to OpenRouter (opt-in)
```

A session now plays out as:

1. **Warm-up drill (~30–60 s)** — 3 short sentences exercising your top recurring error, each with
   immediate pass / fail / incomplete feedback. Skipped if you have no qualifying recurring error or
   pass `--no-warmup`.
2. **Listen** — the question + ideal answer (unchanged).
3. **Three timed attempts (4 / 3 / 2 min)** — unchanged recording + transcription; the final round's
   goal is *"all key points within the time budget."*
4. **1–2 spoken follow-ups** — unscripted, grounded in what you actually said; answer each by voice
   within ~60 s. Say *repeat* to replay once (budget not consumed) or *skip*. Skipped if your attempts
   were too short to probe, or with `--no-followups`.
5. **Report** — written to `data/sessions/YYYY-MM-DD-<qid>.md`, now containing: per-pattern trends vs.
   previous sessions, per-attempt **coverage** (covered/partial/missed) with the first→final delta,
   **content errors** (separate from grammar), **pronunciation flags**, and a **Follow-ups** section.

## Other commands

```bash
uv run speakloop trends            # fluency + grammar dashboard, now with per-pattern trend series
uv run speakloop rebuild           # rebuild the derived store (schedule + key points + patterns) from session files
uv run speakloop resume            # finish any session left "analysis pending" (e.g. model was unavailable)
uv run speakloop resume --cloud
uv run speakloop doctor            # health check, now incl. store + new prompt files
```

## Where things live

- **Raw session data (source of truth)**: `data/sessions/*.md` — Markdown + YAML frontmatter,
  `schema_version` still **1**; all new data is additive/optional (old reports still open fine).
- **Derived store (cache, rebuildable)**: `~/.speakloop/store.json` — SRS schedule, key-point cache,
  pattern aggregation. Delete it any time and `speakloop rebuild` (or the next run) recreates it.
- **Editable prompts**: `~/.speakloop/openrouter_followups_prompt.txt`, `…_keypoints…`, `…_coverage…`,
  `…_triage…`, `…_drill…` (seeded on first use from packaged defaults, like the existing cloud/coach
  prompts).
- **Loop config (YAML)**: daily capacity (default 5) and warm-up/follow-up defaults under `~/.speakloop/`.

## Graceful degradation (never lose a recording)

If the language model is unavailable mid-session, the audio and transcripts are saved, the report is
written with the deterministic parts, and the session is marked `analysis_pending`. Run
`uv run speakloop resume` later to finish the analysis over the preserved data. The question stays due
and un-graded until then.

## Validating the slices (acceptance, from the spec)

```bash
uv run pytest tests/unit/interviewer tests/unit/triage tests/unit/coverage \
              tests/unit/srs tests/unit/warmup tests/unit/store   # per-module units (stubbed engines)
uv run pytest tests/contract        # JSON-schema validation for each new LLM call
uv run pytest tests/integration     # daily-loop end-to-end (stubbed), rebuild round-trip, resume, back-compat
```

- **No hallucination in grammar evidence** (SC-003) and **mishearings only in pronunciation flags**
  (SC-006): assert against the labeled `tests/fixtures/transcripts/gold_set.yaml` + `tests/fixtures/triage/`.
- **Artifacts consistent with the ideal answer** (SC-004): seed a contradiction into a generated artifact
  fixture; assert it is corrected or dropped before the report is written.
- **Due queue never empty while anything is below mastery** (SC-005) and **poor → 1 day, fair → 2 days**:
  assert from `srs` unit tests + the store.
- **Old reports still parse** (SC-012): parse every fixture under `tests/fixtures/sessions/` unchanged.
