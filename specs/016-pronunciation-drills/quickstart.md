# Quickstart: Pronunciation Drills (016)

## What it is

An optional **read-aloud** pronunciation-practice stage that runs in the otherwise-idle time while
your spoken-answer feedback is generated. You read a short sentence aloud; the tool scores your
pronunciation **against the known text** and tells you which sounds were off, with a one-line tip. A
**Pronunciation** section is appended to the session report. It is **opt-in**, **engine/memory-gated**,
and **offline after a one-time download**.

## Enabling / disabling

`loop.yaml` (`~/.speakloop/loop.yaml`) — optional, hand-edited like the other keys:

```yaml
pronunciation_drills: auto      # auto (default) | on | off
pronunciation_min_free_mb: 4500 # optional; free-RAM needed before drills are offered
```

- **auto** (default): offer drills when it's safe to load the model; skip (with a reason) when not.
- **on**: run drills whenever safe, without the per-session prompt.
- **off**: never — no gate check, no offer, no model load.

Per-run override: `speakloop practice --drills` (force the offer this run) / `--no-drills` (skip this
run). The safety gate still applies — `--drills` does not bypass it.

## When are drills offered? (the safety gate)

The pronunciation model is heavy (~1.3 GB on disk, ~2–3 GB in memory). The tool **never** loads it when
that would risk freezing your machine:

- **Cloud feedback engine** (`--engine openrouter` / `--engine claude`) + enough free RAM → **drills
  offered**. The local feedback model isn't resident, so there's room.
- **Local feedback engine** (`--engine local`, the default) → **drills skipped** by default, with a
  plain-language reason: adding the pronunciation model to the resident Qwen model would likely exceed
  memory. Switch to a cloud engine (or `speakloop setup`) to enable drills.
- **Low free memory** (below the threshold) → skipped with a low-memory reason.

If drills are skipped but you insist, the tool offers an explicit override behind a clear
**"this may freeze your machine"** confirmation.

## First run

The first time you opt into drills, the tool discloses the model size and asks for consent, then
downloads it through the same resilient (parallel, resumable) downloader used for every other model.
A user who never opts into drills never downloads it.

## What you see

```
✓ Attempt 3 recorded.
Pronunciation drills are available (your local feedback model isn't resident). Try a few while your
feedback is prepared? [Y/n] y

Read aloud:  The wrapper around the object adds a thin layer.
  ● REC … (space = done)
  → The w in "wrapper" sounded off. (suggestion: it may have come out closer to r)
    Tip: round your lips, don't curl your tongue back — 'wuh', not 'ruh'.
  Want a quick drill?  west / rest …

…(feedback finished in the background)…
Report written: data/sessions/2026-06-12-q07.md
```

The combined report (grammar/coaching **plus** the Pronunciation section) appears only after **both**
the drills and the feedback finish.

## Honest calibration

Detection ("a sound was off") is reliable. The specific guess ("heard as r") is shown as a
**suggestion**, never a verdict — phone-level diagnosis is hard and sometimes wrong, so don't treat it
as gospel.

## Not included (live-only / future)

- `speakloop resume` re-runs only the text feedback over saved transcripts; it does **not** re-run
  drills (there's no saved read-aloud audio).
- `--listen-only` sessions have no attempts/feedback wait, so no drills.
- Out of scope (future): prosody/stress/intonation scoring, scoring your spontaneous answers, and
  auto-generating drills from the current question.

## Manual test checklist

1. **Safe path**: `loop.yaml engine: openrouter` (or `--engine claude`) on a machine with ≥4.5 GB
   free → run `speakloop practice`, finish 3 attempts → drills are offered; read "wrapper" as "rapper"
   → the **w** is flagged; report has a Pronunciation section; report shows after both finish.
2. **Unsafe (local)**: `engine: local` → drills are declined with the plain-language Qwen-memory
   reason; the model is **not** loaded.
3. **Override**: on the unsafe path, accept the freeze-warned `[y/N]` → model loads (interactive only).
4. **Opt-in download**: first opt-in shows size + consent and uses the aria2 path; declining downloads
   nothing and the session continues.
5. **Never-opted-in**: run normal local sessions → no extra download, `doctor` shows the model as
   optional/absent without FAIL, `speakloop --help` loads no model.
