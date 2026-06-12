"""Resource-aware + engine-aware safety gate (016, P3 — the heart of the feature).

Decides whether it is safe to load the ~2–3 GB pronunciation model, from (a) the
active feedback engine and (b) live available RAM. NEVER loads the model — it only
decides; the CLI loads only on SAFE (or an explicit freeze-warned override).

`psutil` is imported function-local and the gate degrades gracefully if it is
unavailable. No network. See contracts/safety-gate.md + research D5.
"""

from __future__ import annotations

from dataclasses import dataclass

# Local feedback engine — its model dominates the 18 GB budget, so adding the
# pronunciation model on top is never safe by default (SC-001).
_LOCAL_ENGINE = "local"


@dataclass(frozen=True)
class SafetyDecision:
    safe: bool
    reason: str  # plain-language English; ALWAYS carries a remediation hint when unsafe
    available_mb: int | None
    engine: str


def _measure_available_mb() -> int | None:
    """Live available RAM in MB, or None if it can't be read (psutil absent)."""
    try:
        import psutil  # function-local: keeps CLI import light and degrades gracefully
    except Exception:  # noqa: BLE001 — any import/runtime failure ⇒ "unknown"
        return None
    try:
        return int(psutil.virtual_memory().available / (1024 * 1024))
    except Exception:  # noqa: BLE001
        return None


def assess_safety(
    engine: str,
    *,
    min_free_mb: int,
    available_mb: int | None = None,
) -> SafetyDecision:
    """Return a SAFE/UNSAFE decision. ``available_mb`` is injectable for tests; when
    None it is measured via psutil (function-local)."""
    eng = (engine or "").strip().lower() or _LOCAL_ENGINE

    # Rule 1 (most important): the local feedback model is/will be resident → never safe.
    if eng == _LOCAL_ENGINE:
        return SafetyDecision(
            safe=False,
            reason=(
                "You're using the local Qwen feedback engine; loading the pronunciation "
                "model on top of it would likely exceed your machine's memory and freeze it. "
                "Switch to a cloud engine (`--engine openrouter` / `--engine claude`, or "
                "`speakloop setup`) to enable drills."
            ),
            available_mb=None,
            engine=eng,
        )

    # Cloud engine: the local feedback model is not resident → check live free memory.
    avail = available_mb if available_mb is not None else _measure_available_mb()

    if avail is None:
        # Can't read free memory; a cloud engine is active so proceed cautiously.
        return SafetyDecision(
            safe=True,
            reason=(
                "Drills are available (couldn't read free memory; proceeding because a "
                "cloud feedback engine is active)."
            ),
            available_mb=None,
            engine=eng,
        )

    if avail >= min_free_mb:
        return SafetyDecision(
            safe=True,
            reason=(
                "Drills are available — your local feedback model isn't resident, so there's "
                "room for the pronunciation model."
            ),
            available_mb=avail,
            engine=eng,
        )

    return SafetyDecision(
        safe=False,
        reason=(
            f"Only {avail} MB free; the pronunciation model needs ~3 GB. Close some apps and "
            "retry, or skip drills this session."
        ),
        available_mb=avail,
        engine=eng,
    )


def assess_standalone_safety(
    *,
    min_free_mb: int,
    available_mb: int | None = None,
) -> SafetyDecision:
    """RAM-only safety decision for the standalone ``speakloop pronounce`` mode (017, FR-011).

    Unlike the interview gate (``assess_safety``), there is **no feedback engine resident** in
    standalone mode, so the 016 rule "local engine ⇒ unsafe" does NOT apply — only live available
    memory matters. The interview gate is left unchanged; this is a distinct variant (research D5,
    contracts/standalone-gate.md). ``available_mb`` is injectable for tests; when None it is
    measured via psutil (function-local). The CLI loads the model only on SAFE or an explicit
    freeze-warned override."""
    avail = available_mb if available_mb is not None else _measure_available_mb()

    if avail is None:
        # Can't read free memory; no feedback model is resident, so proceed cautiously.
        return SafetyDecision(
            safe=True,
            reason="Drills are available (couldn't read free memory; proceeding).",
            available_mb=None,
            engine="standalone",
        )

    if avail >= min_free_mb:
        return SafetyDecision(
            safe=True,
            reason="Drills are available — there's room for the pronunciation model.",
            available_mb=avail,
            engine="standalone",
        )

    return SafetyDecision(
        safe=False,
        reason=(
            f"Only {avail} MB free; the pronunciation model needs ~3 GB. Close some apps and "
            "retry, then run `speakloop pronounce` again."
        ),
        available_mb=avail,
        engine="standalone",
    )
