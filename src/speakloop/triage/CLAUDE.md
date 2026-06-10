# triage

## Purpose

The trustworthy-feedback gate (010-interview-loop, P4), pulled into the
Foundational layer because every other story's analysis depends on it. Two jobs:
**(1)** deterministically drop ASR hallucinations BEFORE grammar/coverage/metrics so
no phantom text ever reaches grammar evidence (SC-003/FR-028), and report likely
pronunciation **mishearings** separately (FR-026); **(2)** fact-check every generated
learning artifact against the ideal answer before the report is written (FR-027).

## Public interface

- `hallucination.filter_hallucinations(transcript) -> TriageResult` — **deterministic,
  no LLM.** Drops spans on VAD-silence overlap, Whisper decode signals
  (`no_speech_prob`/`avg_logprob`/`compression_ratio`), or a phantom-phrase match.
  No-op when the transcript carries no per-segment metadata (Parakeet path).
- `hallucination.classify_segment(text, *, no_speech_prob=, avg_logprob=,
  compression_ratio=, vad_silence=) -> (SpanClass, signal)` — the per-segment rule.
- `hallucination.TriagedSpan`, `hallucination.TriageResult`, `SpanClass`.
- `mishearing.detect_mishearings(real_text, llm, *, system_prompt) -> list[TriagedSpan]`
  — LLM-assisted; **enrichment only** (returns [] on no-model / failure, never raises
  into the loop).
- `consistency.check_artifact(artifact, ideal_answer, llm, *, system_prompt) ->
  ConsistencyVerdict` + `consistency.resolve(artifact, verdict) -> str | None`
  (keep / replace-with-correction / drop; **withhold** on a failed check).
- `prompts.load_triage_prompt()` (seeds `~/.speakloop/openrouter_triage_prompt.txt`),
  `prompts.load_consistency_prompt()` (packaged, read directly).

## Dependencies

- Internal: `speakloop.asr` (`Transcript`/`SegmentMeta`), `speakloop.config` (paths),
  `speakloop.llm` (`LLMEngine`/`LLMEngineError`), and `feedback.grammar_analyzer._extract_json`
  (the shared JSON recovery ladder — reused, not re-implemented).
- **No engine package imported** (Principle V); the hallucination filter is stdlib-only.

## Consumers

`sessions` (the coordinator runs the hallucination filter before grammar and
attaches pronunciation flags), `cli` (consistency check before report write).

## File map

- `hallucination.py` — deterministic filter + shared `TriagedSpan`/`TriageResult` types.
- `phantom_phrases.txt` — curated Whisper silence phantoms (data file).
- `mishearing.py` — LLM mishearing classifier (enrichment).
- `consistency.py` — artifact fact-check + resolution.
- `prompts.py`, `triage_prompt_default.txt`, `consistency_prompt_default.txt` — prompts.

## Common modification patterns

- **Tune the hallucination thresholds**: edit the constants at the top of
  `hallucination.py` (kept equal to Whisper's own decode guards).
- **Extend the phantom list**: add a line to `phantom_phrases.txt` (data, not code).

## Traps

- The hallucination filter MUST run **before** grammar analysis (not after, unlike the
  legacy `feedback/coherence.py` garble filter) so hallucinated text never reaches the
  analyzer or the metrics.
- Mishearing detection is enrichment and the hallucination guarantee is heuristic, so a
  down LLM weakens flags but never lets a hallucination into grammar evidence.

## Pointers

- Root map: [`../../../CLAUDE.md`](../../../CLAUDE.md);
  contracts: `specs/010-interview-loop/contracts/llm-calls.md` (C4, C5).
