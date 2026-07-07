# triage

## Purpose

Trustworthy-feedback gate (010-interview-loop, P4). Two jobs: **(1)** deterministically
drop ASR hallucinations BEFORE grammar/coverage/metrics — so no phantom text ever reaches
grammar evidence (SC-003/FR-028); **(2)** fact-check every generated learning artifact
against the ideal answer before the report is written (FR-027).

## Public interface

- `hallucination.filter_hallucinations(transcript) -> TriageResult` — deterministic, no LLM.
  Drops spans on VAD-silence overlap, Whisper decode signals, or phantom-phrase match.
  No-op when transcript carries no per-segment metadata (Parakeet path).
- `hallucination.classify_segment(text, *, no_speech_prob=, avg_logprob=, compression_ratio=,
  vad_silence=) -> (SpanClass, signal)` — per-segment rule engine.
- `hallucination.TriagedSpan`, `hallucination.TriageResult` — shared data types.
  `TriageResult.summary` property returns `{"real": N, "mishearing": N, "hallucination_dropped": N}`.
- `mishearing.detect_mishearings(real_text, llm, *, system_prompt) -> list[TriagedSpan]` —
  LLM-assisted enrichment; returns `[]` on any failure, never raises into the loop.
- `consistency.check_artifact(artifact, ideal_answer, llm, *, system_prompt) -> ConsistencyVerdict`
  — legitimately receives `ideal_answer` (it is the reference; see llm-calls.md exceptions).
- `consistency.resolve(artifact, verdict) -> str | None` — keep / replace / drop; `None` = withhold.
- `prompts.load_triage_prompt()`, `prompts.load_consistency_prompt()`.

## Dependencies & consumers

- Internal: `speakloop.asr` (`Transcript`/`SegmentMeta`), `speakloop.config` (paths),
  `speakloop.llm` (`LLMEngine`/`LLMEngineError`). JSON recovery: shared `feedback.json_recovery.extract_json`
  ladder (IMP-034; see `src/speakloop/feedback/CLAUDE.md`).
- `hallucination` imported at `sessions/coordinator.py` module level (line 33) — it is
  stdlib-only so this is a minor, intentional exception to the function-local pattern.
- Consumers: `sessions` (hallucination filter before every transcript — including follow-up
  recordings, `coordinator.py:509`), `cli` (consistency check before report write).

## File map

- `hallucination.py` — deterministic filter; threshold constants `NO_SPEECH_PROB_MAX=0.6`,
  `AVG_LOGPROB_MIN=-1.0`, `COMPRESSION_RATIO_MAX=2.4` (lines 26-28; match Whisper's own
  decode guards); `_phantom_phrases()` is `@lru_cache(maxsize=1)` (lines 72-82) — adding a
  line to `phantom_phrases.txt` takes effect on the NEXT process, not the current one.
- `phantom_phrases.txt` — curated Whisper silence phantoms (data file, not code).
- `mishearing.py` — LLM mishearing classifier (enrichment only).
- `consistency.py` — artifact fact-check + resolution.
- `prompts.py`, `triage_prompt_default.txt`, `consistency_prompt_default.txt` — prompt files.

## Invariants & traps

- Run hallucination filter BEFORE grammar analysis (not after). Hallucinated text must never
  reach the analyzer or the metrics.
- `phantom_phrases.txt` edits need a new process to take effect (LRU cache).
- Mishearing is enrichment: a down LLM weakens flags but never lets a hallucination into
  grammar evidence (the deterministic filter already ran).
- `consistency.check_artifact` withholds (returns `None` via `resolve`) rather than showing an
  unchecked artifact — wrong feedback is worse than none.

## Common modification patterns

- **Tune thresholds**: edit the three constants at `hallucination.py:26-28`.
- **Extend phantom list**: add a line to `phantom_phrases.txt`; restart the process.

## Pointers

- Root CLAUDE.md: `../../../CLAUDE.md`. LLM degradation contract + `ideal_answer` boundary:
  `.claude/rules/llm-calls.md` (O7, O8). Contracts: `specs/010-interview-loop/contracts/` (C4, C5).
