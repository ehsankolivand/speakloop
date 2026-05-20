# Quickstart — Post-Session Interactive Debrief

Exercise the feature end-to-end on a single machine. Assumes the v1 setup works
(`uv run speakloop --help` returns, Phase A/B already usable).

## Prerequisites

- macOS arm64 (Apple Silicon; designed for M3 Pro 18 GB).
- `uv` installed; repo cloned.
- A working microphone and audio output (`uv run speakloop doctor` is green).
- For the full grammar debrief (US1+US3), the Phase-C LLM model installed:
  `uv run speakloop practice` will offer the download on first Phase-C use. The
  debrief still runs **without** it (graceful degradation — see below).

## Happy path — full Phase-C debrief

```bash
uv run speakloop practice
```

1. Pick a question; listen to the question + ideal answer (existing listen loop).
2. Press **space** to begin; complete the 4/3/2 cycle (attempts 1→2→3).
3. The report is written under `data/sessions/` (as before) — but instead of
   returning to the shell, the **debrief renders in place**:
   - A bordered **"Top priority for next session"** banner.
   - **Grammar pattern cards**, ranked by impact, each three lines:
     `You said: …` / `Better: …` / `Because: …`.
   - A **trend-coloured** attempt table (WPM and filler density green/yellow/red).
   - **Collapsed transcripts** (first ~10 words + "+143 words").
4. The announcement appears: `🔊 Reading your feedback aloud — press any key to
   skip.` Audio reads the narrative → top priority → each pattern's explanation
   and corrected version, highlighting the active section and showing
   `3 of 6 sections`.
5. Press **any key** to skip the rest of the audio, or let it finish.
6. The menu appears: **(r) replay · (n) new · (q) quit** (default **r**).
   - **r / replay / Enter** → screen clears, straight back to "press space to
     begin attempt 1" for the **same** question in **< 3 s**, no model reload.
   - **n / new** → question picker.
   - **q / quit** → back to the shell.

## Skip audio entirely (power user)

```bash
uv run speakloop practice --no-audio
```

No audio plays; the visual debrief and menu appear immediately after the report
is written.

## Verifying the success criteria locally

- **SC-004 (replay < 3 s, no reload)**: choose **r** at the menu; the next
  "press space to begin attempt 1" prompt should appear in under 3 seconds with
  no "Loading models…" line. (Engines were constructed once at launch.)
- **SC-005 (≤ 90 s debrief)**: time from attempt 3 ending to an actionable menu
  for a 3-pattern report.
- **SC-002 / SC-003 (accurate, anchored feedback)**: run the gold-set test:
  ```bash
  uv run pytest tests/unit/feedback -q          # catalog, coherence, ranking, narrative
  uv run pytest tests/integration/phase_c_debrief_test.py -q
  ```
  Inspect a generated report and confirm: every pattern has a catalog-accurate
  label, every `quote` is verbatim and coherent (no "Killing RT check"-style
  garble), and ≥ 80% of fixes carry a concrete `corrected` differing from the
  quote.

## Graceful degradation checks

- **No LLM model** — temporarily point models away (or test before installing the
  LLM): the debrief still runs on Phase-B content and the grammar area shows
  exactly: `Grammar pattern analysis is available when the LLM model is
  installed.`
- **TTS failure** — with audio enabled but output unavailable, the visual debrief
  still renders and the menu appears immediately (no hang).
- **First-time line** — with an empty `data/sessions/`, the first debrief shows
  the orientation line above the report; subsequent sessions do not.

## What changed vs v1 (orientation for reviewers)

- New module `src/speakloop/debrief/` (own `CLAUDE.md`) — render + audio + menu.
- `feedback/` gains a Persian-L1 catalog (`persian_l1_catalog.yaml` +
  `catalog.py`), a coherence filter (`coherence.py` + `common_words.txt`), a
  deterministic narrative/top-priority (`narrative.py`); the grammar analyzer and
  report builder are upgraded; frontmatter gains additive fields
  (`schema_version` stays **1**).
- `sessions/coordinator.run_session(...)` now returns the `Session` plus the path;
  `cli/practice.py` runs the listen → session → debrief → menu loop with resident
  engines and adds `--no-audio`.
- **No new third-party dependencies.**
