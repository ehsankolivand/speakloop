# metrics

## Purpose

Per-attempt fluency metric computation. Deterministic, transcript-only — no LLM dependency,
no model packages.

## Public interface

- `compute_all(transcript) -> dict` — runs every metric in one call.
- `speech_rate.compute(transcript) -> (words_total, speech_rate_wpm)`.
- `pauses.compute(words) -> (pauses_count, mean_pause_ms)` — 250 ms threshold.
- `fillers.compute(text) -> (filler_words_count, filler_density_per_100_words)`.
- `self_corrections.compute(text) -> count`.

## Dependencies

- Internal: `speakloop.asr` (the `Transcript`/`WordTiming` types only).
- Explicitly NONE: must not import `speakloop.llm` — this is a transcript-only signal
  (`self_corrections.py:3`).

## Consumers

`sessions`.

## File map

- `__init__.py` — `compute_all` aggregator.
- `speech_rate.py`, `pauses.py`, `fillers.py`, `self_corrections.py` — one metric each.

## Common modification patterns

- **Add a metric**: add a `compute()` in a new file and call it from `compute_all`.
- **Tune a threshold** (e.g. pause 250 ms): edit that metric file only.

## Never do

- Import `speakloop.llm` or any model package — metrics are deterministic and offline.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md).
