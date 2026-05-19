# metrics

Per-attempt fluency metric computation. Deterministic, transcript-only,
no LLM dependency.

**Public surface**:

- `speech_rate.compute(transcript) -> (words_total, speech_rate_wpm)`.
- `pauses.compute(words) -> (pauses_count, mean_pause_ms)` — 250 ms threshold (FR-012b).
- `fillers.compute(words) -> (filler_words_count, filler_density_per_100_words)`.
- `self_corrections.compute(words) -> count` (FR-012c).
