# Reproduction fixture — kotlin-coroutines failure session (FR-010)

This is the **mandatory acceptance gate** for 003-asr-l2-accent-accuracy. It is a
**local-only** gate: the recordings are your own voice and are **never committed**
(see `.gitignore`; Constitution Principle III / spec privacy decision). Without
the recordings the gate **skips cleanly**, so model-free CI stays green — but the
feature is not "done" until it runs green here on your audio.

## How to run it

1. Drop the original failure-session recordings into this folder:
   - `attempt-1.wav`, `attempt-2.wav`, … (the 4/3/2 attempts that misheard
     "threads"→"trades", "coroutine"→"quarantine", "shared pool"→"shaded pool").
2. Add `hand_transcript.txt` — your verbatim ground-truth transcription of those
   recordings (one attempt per line, or whitespace-separated; used for the SC-B
   technical-token WER comparison).
3. (Optional) Fill `baseline_parakeet.json` `attempts` with the previous
   pipeline's transcripts, or leave the documented substitutions for reference.
4. Run:

   ```bash
   uv run pytest -m repro -v
   ```

## What it checks

- **SC-A**: each `target_token` in `expected_tokens.yaml` transcribes correctly in
  ≥ 4/5 occurrences with the new pipeline (Whisper + domain biasing + VAD).
- **SC-B**: ≥ 30% relative reduction in technical-token word error rate vs the
  baseline, measured on the **hand-labeled** tokens.
