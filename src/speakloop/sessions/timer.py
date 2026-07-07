"""Per-attempt time budgets (4 min / 3 min / 2 min).

The recording countdown/progress itself is rendered by `session_ui.make_recording_progress`
plus the inline `_ticker` thread in `coordinator._record_stage` (012); the old rich.progress
`run()` here had no production caller and was removed (IMP-030).
"""

from __future__ import annotations

# Per FR-005..FR-007: 4 min / 3 min / 2 min budgets.
BUDGETS = (240, 180, 120)


def time_budget_for(ordinal: int) -> int:
    if ordinal < 1 or ordinal > 3:
        raise ValueError(f"ordinal must be 1..3, got {ordinal}")
    return BUDGETS[ordinal - 1]
