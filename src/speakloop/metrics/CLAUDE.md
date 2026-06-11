# metrics

## Purpose

Per-attempt fluency metric computation. Deterministic, transcript-only — no LLM or
model-package dependency. All `compute` functions return `dict[str, float | int]`.

## Public interface

- `compute_all(transcript, *, vad_regions=None) -> dict[str, float | int]`
  (`__init__.py:6`) — runs all four metrics in one call. `vad_regions` (010): optional
  tuple of `(start_seconds, end_seconds)` real-speech regions; when supplied, hallucinated
  spans do not skew rate or pauses. `None` → byte-identical to pre-010.
- `speech_rate.compute(transcript, *, real_speech_seconds=None) -> dict` — keys:
  `{"words_total", "speech_rate_wpm"}` (`speech_rate.py:32-40`).
- `pauses.compute(words, *, threshold_ms=PAUSE_THRESHOLD_MS, vad_regions=None) -> dict`
  — keys: `{"pauses_count", "mean_pause_ms"}` (`pauses.py:36-52`).
- `fillers.compute(text) -> dict` — keys: `{"filler_words_count",
  "filler_density_per_100_words"}` (`fillers.py:46-50`).
- `self_corrections.compute(text) -> dict` — key: `{"self_corrections_count"}`
  (`self_corrections.py:51-52`).

## Named constants

- `pauses.PAUSE_THRESHOLD_MS = 250` (`pauses.py:7`) — the single configurable knob.
- `fillers.FILLER_TOKENS` — 10-token tuple: `um`, `uh`, `ah`, `er`, `hmm`, `like`,
  `you know`, `i mean`, `basically`, `actually` (`fillers.py:7-19`). Longest-first
  regex to prevent overlap.
- `self_corrections.REPAIR_MARKERS` — 6-token tuple: `i mean`, `sorry`,
  `let me rephrase`, `actually no`, `what i meant`, `wait` (`self_corrections.py:10-17`).

## Dependencies & consumers

- Internal: `speakloop.asr` (`Transcript`, `WordTiming` types only).
- Must never import `speakloop.llm` or any model package (`self_corrections.py:3`).
- Consumers: `sessions`.

## File map

- `__init__.py` — `compute_all` aggregator.
- `speech_rate.py` — word-count + WPM; uses `real_speech_seconds` when supplied.
- `pauses.py` — inter-word gaps ≥ `PAUSE_THRESHOLD_MS`; `vad_regions` filters
  gaps that span dropped silence/hallucination spans (010, P4).
- `fillers.py` — regex match of `FILLER_TOKENS` (whole-word, case-insensitive).
- `self_corrections.py` — verbatim-repeat pairs + `REPAIR_MARKERS` matches.

## Invariants & traps

- All `compute` functions return dicts; no function returns a tuple or bare scalar.
- `vad_regions` filtering was added in 010 so hallucinated spans do not skew
  rate/pauses; `None` preserves pre-010 byte-identical output.
- Never import `speakloop.llm` — metrics are deterministic and offline.

## Common modification patterns

- Add a metric: new `compute()` in a new file returning a dict; call from `compute_all`.
- Tune pause threshold: edit `PAUSE_THRESHOLD_MS` in `pauses.py` only.
- Add a filler token: extend `FILLER_TOKENS` tuple in `fillers.py`.

## Pointers

- Root map: `../../../CLAUDE.md`
- Testing rules: `.claude/rules/testing.md`
