# Quickstart: Pronunciation Trainer (017)

Builds on 016. The drill block now **plays the target first**, lets you **replay** it, gives a
**bounded retry** when a sound is off, practises **sentences**, and runs **standalone** via
`speakloop pronounce`. Opt-in, offline, engine/memory-gated, read-aloud only — exactly as 016.

## Try it in an interview session (hear → say → see → retry)

```bash
# Use a cloud feedback engine so the safety gate offers drills (the local Qwen engine still skips them).
uv run speakloop practice --engine openrouter --drills
```

During the post-attempt feedback wait, for each drill:
1. You **hear** the target spoken (Kokoro TTS). Press **`r`** to hear it again; press **Space** to record.
2. You **say** it; the tool **shows** which sound was off (detection-led, hedged — 016 calibration).
3. If a sound was flagged, the tool automatically gives you **one more try** on the same item
   (hear → say) and tells you if it **improved**.
4. The combined report (grammar/coaching + a Pronunciation section with retry + "tricky sounds")
   appears after both the drills and the feedback finish.

## Try it standalone (no interview)

```bash
uv run speakloop pronounce              # practise as long as you like; `q` to stop
uv run speakloop pronounce --limit 4    # cap the number of base sentences this run
```

- The gate here is **memory-only** (no feedback engine is resident), so drills are available in the
  common case — even if your default engine is `local`.
- First run: if the pronunciation model or TTS model is missing, you'll get the standard size
  disclosure + consent (the same resilient downloader as every other model). Decline → it exits
  cleanly; nothing downloads silently.
- It needs **no** speech-recognition model (scoring is done directly by the pronunciation model).
- On exit you get a short summary (how many drills, your trickiest sound). No session report is
  written — it's not an interview.

## Config (optional `~/.speakloop/loop.yaml`, silent defaults)

```yaml
pronunciation_drills: auto          # 016: auto | on | off
pronunciation_min_free_mb: 4500     # 016: free-RAM threshold (reused by the standalone gate)
pronunciation_tts_playback: true    # 017: play the target before each drill
pronunciation_retries: 1            # 017: bounded retries per flagged item (0 = 016 one-shot; max 3)
```

## Check status

```bash
uv run speakloop doctor    # Pronunciation drills: model presence (opt-in), settings, gate estimate,
                           #   and standalone availability (RAM-only). Never FAILs the exit code.
```

## Behaviour & guarantees

- **Offline**: after the one-time download, the trainer makes zero network calls (TTS, scoring, and
  canonical phonemes are all local/bundled).
- **Byte-identical**: a session that runs no drills produces the same report as before this feature.
- **`--help` stays model-free**: `speakloop --help` loads no engine/model package, including the new
  `pronounce` command.
- **Degrades gracefully**: no TTS/audio → no hear-first (records + scores like 016); no history →
  curated drill order; low memory → drills skipped with a plain reason + freeze-warned override.

## Manual test plan (verify before merge)

1. **Interview, cloud engine**: confirm the target is spoken before each drill, `r` replays it, a
   flagged sound triggers a bounded retry, and the report appears only after drills + feedback finish.
2. **Standalone**: `speakloop pronounce` runs the loop with the RAM-only gate (works even with
   `engine: local` configured); `q` exits with a summary; no report file is written.
3. **Sentences**: confirm base items are sentences (spoken + shown); a flag routes into word minimal-pairs.
4. **Weak-sound focus**: after flagging a contrast, confirm the next run repeats that contrast first.
5. **No-drills byte-identical**: a `--no-drills` session report is byte-identical; `--help` loads no model.
6. **Correctness harness**: on a model-equipped machine, `uv run pytest -m live_pron` passes (every
   bundled drill's own TTS rendering scores clean).
```
