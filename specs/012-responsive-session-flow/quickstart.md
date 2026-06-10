# Quickstart: Responsive, Transparent & Faster Practice Session

## What changes for the learner

```bash
# Same command — now transparent and faster.
uv run speakloop practice

#  ▶ playing question…            (space=skip · r=replay)
#  ▶ playing ideal answer…        (space=skip · r=replay)        # skippable; auto-off via config
#  Recording in 3 · 2 · 1
#  ● REC attempt 1 — 12s / 240s   ▕███▌            ▏  (space/Enter=stop)
#  ⠋ transcribing…
#  … (attempt 2, attempt 3) …
#  ⠋ generating follow-up…        # starts the moment the final transcript lands
#  ▶ playing follow-up…           (space=skip · r=replay · s=skip follow-up)
#  Recording in 3 · 2 · 1
#  ● REC follow-up 1 — 8s / 60s   ▕██▌             ▏  (space/Enter=stop · s=skip)
#  ⠋ analyzing… (grammar, coverage, coaching running concurrently on claude/openrouter)
#
#  ── Session summary ───────────────────────────────
#   Grade: good   Coverage: 40% → 85%   Top fix: article use ("a"/"the")
#   Next due: 2026-06-13   Report: data/sessions/2026-06-10-q01.md
```

### New controls (single key; only the keys valid right now are shown)

| Key | Where | Effect |
|-----|-------|--------|
| `space` / `Enter` | during playback | skip the current clip |
| `space` / `Enter` | during recording | stop recording (done speaking) |
| `r` | during/after playback | replay the current clip |
| `s` | during a follow-up | skip the whole follow-up |
| `q` | listen-loop idle | quit |

### New config (`~/.speakloop/loop.yaml`, optional)

```yaml
autoplay_ideal_answer: false   # skip auto-playing the ideal answer on repeat reviews
analysis_concurrency: 3        # concurrent analysis calls on claude/openrouter (default 3)
```

### See where time went

```bash
uv run speakloop practice --timings
# … per-stage table at the end; the same breakdown is saved in the report frontmatter.
uv run speakloop resume --timings           # also available on resume
```

## What stays the same

- Same prompts, models, schemas, and report semantics. `schema_version` stays **1**; a
  report with no `timings` key is byte-identical to today.
- The default local path stays fully offline; local analysis stays serial (single in-process
  model). Concurrency applies only to the parallel-safe `claude` / `openrouter` engines and
  produces a **byte-identical report**.
- Recordings and transcripts survive a Ctrl-C / crash mid-analysis exactly as today; the
  session is resumable.
- Zero new dependencies (raw keypresses via stdlib termios/tty/select; display via the
  existing `rich`).

## For the developer

- New seams (all injectable, all faked in tests):
  - `sessions/keyboard.py` — `KeyReader` (`RawKeyReader` / `NullKeyReader` / `FakeKeyReader`).
  - `feedback/timings.py` — `StageTimer` (injectable clock).
  - `sessions/analysis.py` — the analysis DAG executor (serial + concurrent strategies).
  - `audio/playback.play_interruptible(...)` + `warm_output_device()`.
  - `sessions/session_ui.py` — the one-state-at-a-time `rich` display + countdown.
- Run the suite (never touches the real binary / mic / keyboard):
  ```bash
  uv run pytest -q
  ```
- Re-measure baseline vs after (manual; uses the real engines, capped real claude calls):
  ```bash
  uv run python specs/012-responsive-session-flow/research/measure_tts_asr.py
  uv run python specs/012-responsive-session-flow/research/measure_claude.py   # ≤ ~14 real calls
  ```
