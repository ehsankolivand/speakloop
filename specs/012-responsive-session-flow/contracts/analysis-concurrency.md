# Contract: Concurrent Analysis & Report Equivalence

## Engine parallel-safety capability (FR-026)

Each `LLMEngine` implementation declares a class attribute:

```python
class ClaudeCodeEngine:  parallel_safe = True    # separate subprocess per call
class OpenRouterEngine:  parallel_safe = True    # independent HTTP requests
class QwenEngine:        parallel_safe = False   # single in-process MLX model — must stay serial
```

The CLI reads `getattr(engine, "parallel_safe", False)` for the engine it built and passes
`analysis_parallel_safe: bool` + `analysis_concurrency: int` into `run_session`. Default-false
is the safe fallback for any engine that does not declare the attribute.

## The analysis DAG (gates preserved exactly)

```
grammar (root) ─┬─ (phase==C) keypoints ── coverage
                └─ (phase==C) coaching  ── consistency
mishearing (independent of grammar)
followups  (independent of grammar; ≤12s-critical → scheduled first)
```

- `coverage` and `coaching` run **only if `grammar` succeeded** (today's `phase == "C"` gate).
- `consistency` runs **only if `coaching` produced output** (today's gate).
- These gates are identical to the current serial code — they are what makes the report
  identical regardless of execution strategy.

## Two strategies, one result-set

| | Serial strategy | Concurrent strategy |
|--|----------------|---------------------|
| When | `parallel_safe == False` (local Qwen) or cap == 1 | `parallel_safe == True` (claude/openrouter) |
| How | jobs run in fixed topological order on the calling thread | `ThreadPoolExecutor(max_workers=cap)` honoring the DAG |
| Result | named result slots | named result slots (identical values) |
| Store writes | main thread, post-compute, fixed order | main thread, post-join, fixed order |
| Report assembly | fixed field order | fixed field order |

**Invariant (FR-027, SC-006):** given identical engine outputs for each call, the serial and
concurrent strategies produce a **byte-identical report**. Guaranteed because:

1. Jobs are **pure** (no shared mutable state during execution).
2. Results are collected into **named slots**, never positionally / completion-ordered.
3. Store mutations (key-point cache write, pattern-series append) happen **only on the main
   thread after all jobs complete**, in the same fixed order in both strategies.
4. The `Session` is assembled from the slots in a **fixed field order** (today's order).

## Per-call degradation (FR-028)

Each job is wrapped so its own failure is captured as that dimension's degradation and never
propagates to siblings:

- `grammar` fails → `phase_c_error` + `analysis_pending`; coverage/coaching skipped (today's
  behavior — they were gated on grammar success anyway).
- `mishearing` fails → enrichment returns `[]` (today's behavior; never blocks).
- `coverage` fails → coverage skipped + `analysis_pending` (today's behavior).
- `coaching` fails → `coach_error`; `consistency` fails → coaching withheld/uncorrected
  (today's behavior).
- A failed job in the concurrent pool sets ONLY its slot to a failure marker; the executor
  collects the rest. One failing call never poisons another (SC: equivalence-with-failure test).

## Crash safety (FR-029)

- `attempt-*.wav` + transcripts are written to scratch **before** analysis begins (unchanged).
- The report (source of truth) is written atomically once analysis completes; the store is
  saved after the report.
- A Ctrl-C / crash mid-analysis leaves the recordings + transcripts intact and the session
  resumable via `speakloop resume`, exactly as today. The `ThreadPoolExecutor` is created with
  a `with` block so its worker threads are joined/cancelled on exit; an abort cancels pending
  futures and re-raises `AbortedError` after the recordings are already safe on disk.

## Scheduling for the ≤12s-to-follow-up target (SC-002)

- `followups` generation is submitted/sequenced **first**, right after the final transcription
  + triage — never behind grammar/coverage/coaching.
- Parallel-safe engine: `followups` runs concurrently with `grammar` etc.; as soon as it
  returns, the interactive follow-up Q&A starts while the rest of analysis continues in the
  background pool. Reorder is report-safe (follow-up entries are independent of main grammar).
- Serial engine: `followups` is generated first in the serial order, then the interactive Q&A,
  then grammar/coverage/coaching. Same result-set → same report.
- Critical path to first follow-up = `attempt_3_transcribe` + `followup_generate`; both are
  measured and the floor is documented in research.md when model latency makes 12 s
  unreachable for a long final attempt.
