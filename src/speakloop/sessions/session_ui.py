"""One-state-at-a-time terminal display for the practice session (012, US1).

Renders exactly one unambiguous state — playing / recording / transcribing /
analyzing — using the already-present ``rich`` (no new dependency). Provides the
pre-recording countdown, the ``● REC`` recording indicator, the analyzing/
transcribing spinners, the per-state control hints, and the compact end-of-session
summary. Everything takes an injected ``Console`` (and, for the countdown, an
injected clock/sleep) so tests render to a ``StringIO`` and never sleep.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager
from enum import Enum

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class SessionState(Enum):
    PLAYING = "playing"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"


# Per-state control hints — show ONLY the keys valid right now (FR-010). Sourced from
# the same map the behavior uses so the hint never drifts from what the keys do.
def control_hint(state: SessionState, *, follow_up: bool = False) -> str:
    if state is SessionState.PLAYING:
        keys = "(space) skip · (r) replay"
        if follow_up:
            keys += " · (s) skip follow-up"
        return keys
    if state is SessionState.RECORDING:
        keys = "(space/Enter) stop when done"
        if follow_up:
            keys += " · (s) skip follow-up"
        return keys
    return ""  # transcribing / analyzing accept no controls


# Countdown ticks ("Recording in 3 · 2 · 1"). Visual-only (~0.5 s/tick); NO TTS so it
# never adds synthesis latency before a recording (clarification Q5).
COUNTDOWN_TICKS = 3
COUNTDOWN_INTERVAL_SECONDS = 0.5


def countdown(
    console: Console,
    *,
    ticks: int = COUNTDOWN_TICKS,
    interval: float = COUNTDOWN_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Render a brief visual ``Recording in 3 · 2 · 1`` cue (FR-004)."""
    nums = " · ".join(str(n) for n in range(ticks, 0, -1))
    console.print(f"[bold]Recording in[/bold] {nums}")
    for _ in range(ticks):
        sleep(interval)


def make_recording_progress(console: Console) -> Progress:
    """A transient ``● REC`` indicator: red marker + elapsed/budget + remaining bar.

    Visually distinct from the playing/transcribing/analyzing states (FR-003). The
    caller adds one task ``progress.add_task("rec", total=budget, label=<label>)`` and
    updates ``completed`` from a ticker (as the coordinator already does)."""
    return Progress(
        TextColumn("[bold red]● REC[/bold red] [bold]{task.fields[label]}[/bold]"),
        BarColumn(),
        TextColumn("{task.completed:.0f}s / {task.total:.0f}s"),
        TimeRemainingColumn(),
        transient=True,
        console=console,
    )


@contextmanager
def working(console: Console, state: SessionState, message: str):
    """Spinner + elapsed timer for a slow blocking op (TRANSCRIBING / ANALYZING).

    Generalizes the previous ``coordinator._analyzing`` so every >2 s operation shows a
    labeled, animated state and the terminal never sits silently (FR-002, SC-007). The
    spinner animates on rich's own refresh thread while the call blocks; transient, so
    the line is cleared on completion; exceptions still propagate to the caller."""
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}[/cyan]"),
        TimeElapsedColumn(),
        transient=True,
        console=console,
    )
    with progress:
        progress.add_task(message, total=None)
        yield


def render_summary(console: Console, session, *, next_due: str | None = None) -> None:
    """Print a compact end-of-session summary so opening the report is optional (US2).

    Shows grade, coverage first→final, top fix, and next due date — sourced from the
    same data written to the report. Degrades honestly: a degraded/analysis-pending
    session states that analysis is pending rather than fabricating a grade (FR-016)."""
    from rich.panel import Panel

    lines: list[str] = []
    if getattr(session, "analysis_pending", False):
        lines.append("[yellow]Analysis pending[/yellow] — run `speakloop resume` to finish it.")
        grade = getattr(session, "answer_grade", None)
        if grade:
            lines.append(f"Grade (interim): [bold]{grade}[/bold]")
    else:
        grade = getattr(session, "answer_grade", None)
        lines.append(f"Grade: [bold]{grade or '—'}[/bold]")

    cov = _coverage_first_final(session)
    if cov is not None:
        first, final = cov
        lines.append(f"Coverage: {first}% → {final}%")

    top = getattr(session, "top_priority", None)
    if top and top.strip():
        # The top-priority text can be multi-line; show the first line only, compact.
        lines.append(f"Top fix: {top.strip().splitlines()[0]}")

    if next_due:
        lines.append(f"Next due: {next_due}")

    report_id = getattr(session, "session_id", "")
    title = f"Session summary — {report_id}" if report_id else "Session summary"
    console.print(Panel("\n".join(lines), title=title, expand=False))


def _coverage_first_final(session) -> tuple[int, int] | None:
    """Extract (first-attempt %, final-attempt %) from the session coverage records.

    Coverage records carry an ``aggregate`` in 0..1 (coverage/scoring.py); render it as
    a whole percentage, ordered by attempt."""
    records = getattr(session, "coverage", None) or []
    ordered = sorted(
        (r for r in records if isinstance(r, dict) and isinstance(r.get("aggregate"), (int, float))),
        key=lambda r: int(r.get("attempt_ordinal", 0)),
    )
    if not ordered:
        return None
    first = int(round(float(ordered[0]["aggregate"]) * 100))
    final = int(round(float(ordered[-1]["aggregate"]) * 100))
    return first, final
