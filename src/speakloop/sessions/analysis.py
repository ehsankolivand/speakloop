"""Engine-capability-aware analysis executor (012-responsive-session-flow, US3).

Runs a group of named, independent analysis thunks either **serially** (a single
in-process model — the local Qwen engine) or **concurrently** with a bounded cap (a
parallel-safe subprocess/HTTP engine — Claude Code / OpenRouter). Both strategies
return the SAME ``{name: JobResult}`` mapping, so the coordinator assembles the report
from named slots in a fixed order and the two paths produce a **byte-identical report**
given identical model outputs (FR-027, SC-006).

Per-call degradation is preserved: each thunk's exception is captured into its own
``JobResult.error`` and never propagates to a sibling (FR-028). Jobs MUST be pure —
they may read shared state but MUST NOT mutate it; the caller applies any store writes
on the main thread after the group completes, in a fixed order, so concurrency never
reorders persisted state.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class JobResult:
    """The outcome of one analysis thunk: its value, or the exception it raised."""

    value: Any = None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _run_one(fn: Callable[[], Any]) -> JobResult:
    """Run one thunk, capturing any ``Exception`` so a failure degrades only this job.

    ``KeyboardInterrupt`` / ``SystemExit`` (BaseException, not Exception) deliberately
    propagate so an abort is never swallowed."""
    try:
        return JobResult(value=fn())
    except Exception as e:  # noqa: BLE001 — per-call degradation: capture, never crash siblings
        return JobResult(error=e)


def run_group(
    jobs: dict[str, Callable[[], Any]],
    *,
    parallel_safe: bool,
    concurrency: int,
) -> dict[str, JobResult]:
    """Run each named thunk and return ``{name: JobResult}``.

    Serial (insertion order) when the engine is not parallel-safe, the cap is ≤ 1, or
    there is ≤ 1 job; otherwise concurrent via a ``ThreadPoolExecutor`` capped at
    ``min(concurrency, len(jobs))``. Results are keyed by NAME — never by completion
    order — so the caller's assembly is identical regardless of execution strategy.
    """
    results: dict[str, JobResult] = {}
    if not parallel_safe or concurrency <= 1 or len(jobs) <= 1:
        for name, fn in jobs.items():
            results[name] = _run_one(fn)
        return results

    workers = min(concurrency, len(jobs))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {name: ex.submit(_run_one, fn) for name, fn in jobs.items()}
        # _run_one never raises, so fut.result() returns a JobResult for every job.
        for name, fut in futures.items():
            results[name] = fut.result()
    return results
