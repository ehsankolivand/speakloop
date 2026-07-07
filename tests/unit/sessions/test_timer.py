"""T059 — per-attempt time budgets."""

from __future__ import annotations

import pytest

from speakloop.sessions import timer

pytestmark = pytest.mark.unit


def test_budgets_are_4_3_2_minutes():
    assert timer.time_budget_for(1) == 240
    assert timer.time_budget_for(2) == 180
    assert timer.time_budget_for(3) == 120


def test_invalid_ordinal_raises():
    with pytest.raises(ValueError):
        timer.time_budget_for(0)
    with pytest.raises(ValueError):
        timer.time_budget_for(4)
