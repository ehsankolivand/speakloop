"""Per-session stage timing instrumentation (012-responsive-session-flow, US3).

`StageTimer` records the wall-clock of each session stage. It is **always-on** and
cheap (two ``perf_counter`` reads per stage); the ``--timings`` flag only gates the
terminal display. ``to_frontmatter()`` builds the additive optional ``timings`` block
written to the report frontmatter (``schema_version`` stays 1); ``render()`` builds a
``rich`` table for the terminal.

The clock is injectable so tests are deterministic and never sleep.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

# Inner shape version of the timings block (NOT the report schema_version, which stays 1).
TIMINGS_SCHEMA = 1


class StageTimer:
    """Accumulate named stage durations for one session.

    Use ``with timer.stage("name"): ...`` for a synchronous stage, or the manual
    ``start(name)`` / ``stop(name)`` pair for a stage whose wall-clock overlaps another
    (e.g. background transcription). ``record(name, seconds)`` appends a duration
    measured elsewhere. ``overlapped=True`` marks a stage whose wall-clock ran hidden
    behind another so a reader does not double-count it.
    """

    def __init__(self, *, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._records: list[dict] = []
        self._open: dict[str, float] = {}
        self._session_start = clock()

    @contextmanager
    def stage(self, name: str, *, overlapped: bool = False) -> Iterator[None]:
        start = self._clock()
        try:
            yield
        finally:
            self.record(name, self._clock() - start, overlapped=overlapped)

    def start(self, name: str) -> None:
        """Mark the start of a (possibly overlapped) stage; pair with ``stop``."""
        self._open[name] = self._clock()

    def stop(self, name: str, *, overlapped: bool = False) -> None:
        """Close a stage opened with ``start``; no-op if it was never started."""
        start = self._open.pop(name, None)
        if start is not None:
            self.record(name, self._clock() - start, overlapped=overlapped)

    def record(self, name: str, seconds: float, *, overlapped: bool = False) -> None:
        rec: dict = {"name": str(name), "seconds": round(max(0.0, float(seconds)), 3)}
        if overlapped:
            rec["overlapped"] = True
        self._records.append(rec)

    @property
    def records(self) -> list[dict]:
        return list(self._records)

    def total_seconds(self) -> float:
        return round(max(0.0, self._clock() - self._session_start), 3)

    def to_frontmatter(
        self,
        *,
        analysis_mode: str | None = None,
        analysis_concurrency: int | None = None,
        analysis_wall_seconds: float | None = None,
    ) -> dict:
        """Build the additive ``timings`` frontmatter block (data-model §timings)."""
        block: dict = {
            "schema": TIMINGS_SCHEMA,
            "total_seconds": self.total_seconds(),
        }
        if analysis_mode is not None:
            block["analysis_mode"] = analysis_mode
        if analysis_concurrency is not None:
            block["analysis_concurrency"] = int(analysis_concurrency)
        if analysis_wall_seconds is not None:
            block["analysis_wall_seconds"] = round(max(0.0, float(analysis_wall_seconds)), 3)
        block["stages"] = [dict(r) for r in self._records]
        return block

    def render(self):
        """Return a ``rich`` table of the per-stage breakdown for the terminal."""
        from rich.table import Table

        table = Table(title="Session timings", show_edge=False, pad_edge=False)
        table.add_column("stage")
        table.add_column("seconds", justify="right")
        table.add_column("", justify="left")
        for r in self._records:
            table.add_row(
                r["name"],
                f"{r['seconds']:.1f}",
                "(overlapped)" if r.get("overlapped") else "",
            )
        table.add_row("[bold]total[/bold]", f"[bold]{self.total_seconds():.1f}[/bold]", "")
        return table
