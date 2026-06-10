# Contract: loop.yaml additions & timings frontmatter

## `loop.yaml` additive keys (LoopConfig)

Both follow the existing `LoopConfig` rules: the file is opt-in (never auto-created); an absent
or malformed file falls back to built-in defaults; unknown/invalid values fall back per-key.

```yaml
# ~/.speakloop/loop.yaml  (all keys optional; shown with defaults)
autoplay_ideal_answer: true     # false → don't auto-play the ideal answer (still replayable)
analysis_concurrency: 3         # max concurrent analysis calls on a parallel-safe engine (≥1)
```

| Key | Type | Default | Clamp / fallback |
|-----|------|---------|------------------|
| `autoplay_ideal_answer` | bool | `true` | non-bool → `true` |
| `analysis_concurrency` | int | `3` | `max(1, int(x))`; non-int → `3` |

`LoopConfig` gains two frozen fields with these defaults; `load()` parses them defensively
(mirrors `claude_timeout_seconds`). The local engine ignores `analysis_concurrency` (it is
always serial). No other config changes.

## `timings` frontmatter block

```yaml
timings:
  schema: 1
  total_seconds: <float>            # whole-session wall-clock
  analysis_mode: serial | concurrent
  analysis_concurrency: <int>
  analysis_wall_seconds: <float>    # wall-clock of the analysis group (the SC-003 figure)
  stages:
    - { name: <str>, seconds: <float>, overlapped: <bool?> }
```

Rules:
- Emitted **only when present** (`if session.timings`); a no-timings report is byte-identical
  to today.
- `schema_version` (the report-level key) stays **1**; the inner `timings.schema` versions only
  the timings block's own shape and starts at 1.
- `name` ∈ a fixed vocabulary: `tts_warm`, `listen_synth_question`, `listen_synth_ideal`,
  `asr_warmup`, `warmup_drill`, `attempt_<n>_record`, `attempt_<n>_transcribe`,
  `followup_generate`, `followup_<n>`, `analysis_grammar`, `analysis_mishearing`,
  `analysis_keypoints`, `analysis_coverage`, `analysis_coaching`, `analysis_consistency`.
- `overlapped: true` marks a stage whose wall-clock was hidden behind another (not added to the
  perceived latency). Absent ⇒ `false`.
- Display: `--timings` renders a `rich` table to the terminal at session end. Frontmatter is
  written regardless of the flag (instrumentation is always-on; the flag is display-only).
- Trends/aggregation never read `timings` (informational only).

## CLI

`speakloop practice` and `speakloop resume` gain `--timings` (default `False`):

```
--timings   Print a per-stage timing breakdown at the end of the session.
```

No other flags change. `--timings` is plumbed exactly like `--engine`/`--speed`
(typer option → `practice.run(...)` → `coordinator.run_session(...)`).
