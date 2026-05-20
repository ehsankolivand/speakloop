"""Static seed of high-frequency interview / engineering terms (FR-003b).

These terms always seed the Whisper `initial_prompt` for every session,
independent of the question, so common technical vocabulary is biased even when
a given prompt does not mention it. Source: doc/research_asr_l2_accent.md §B.3.7.

Pure constant — no I/O, no engine imports. Lives in `asr/` only for cohesion
with the domain-context builder that consumes it.
"""

from __future__ import annotations

SEED_TERMS: tuple[str, ...] = (
    "coroutines",
    "threads",
    "mutex",
    "async",
    "await",
    "dispatcher",
    "semaphore",
    "deadlock",
    "race condition",
    "dependency injection",
    "Jetpack Compose",
    "MVI",
    "clean architecture",
    "Kubernetes",
    "Redis",
    "Postgres",
    "REST",
    "gRPC",
    "latency",
    "throughput",
    "idempotent",
)
